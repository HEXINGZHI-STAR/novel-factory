package com.pangu.controller;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.io.*;
import java.nio.file.*;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.stream.Stream;

/**
 * 项目管理API — 骨架层的CRUD
 * 
 * 负责项目创建、章节管理、状态查询。
 * 纯Java操作，不依赖Python。
 */
@RestController
@RequestMapping("/api/projects")
@CrossOrigin(origins = "*")
public class ProjectController {

    private static final Logger log = LoggerFactory.getLogger(ProjectController.class);
    private final Path projectsRoot;

    public ProjectController() {
        Path current = Path.of(System.getProperty("user.dir"));
        this.projectsRoot = current.resolve("../projects").normalize();
        log.info("项目管理控制器初始化，项目根目录: {}", projectsRoot);
    }

    /**
     * GET /api/projects
     * 获取所有项目列表
     */
    @GetMapping
    public ResponseEntity<List<Map<String, Object>>> listProjects() {
        List<Map<String, Object>> projects = new ArrayList<>();
        try {
            if (!Files.exists(projectsRoot)) {
                return ResponseEntity.ok(projects);
            }
            try (Stream<Path> dirs = Files.list(projectsRoot)) {
                dirs.filter(Files::isDirectory).forEach(dir -> {
                    Map<String, Object> info = new LinkedHashMap<>();
                    info.put("name", dir.getFileName().toString());
                    info.put("path", dir.toString());
                    
                    // 统计章节数
                    Path bodyDir = dir.resolve("正文");
                    int chapterCount = 0;
                    if (Files.exists(bodyDir)) {
                        try (Stream<Path> files = Files.list(bodyDir)) {
                            chapterCount = (int) files.filter(f -> f.getFileName().toString().endsWith(".txt")).count();
                        } catch (IOException ignored) {}
                    }
                    info.put("chapters", chapterCount);
                    
                    // 总字数
                    long totalWords = 0;
                    if (Files.exists(bodyDir)) {
                        try (Stream<Path> files = Files.list(bodyDir)) {
                            totalWords = files
                                .filter(f -> f.toString().endsWith(".txt"))
                                .mapToLong(f -> {
                                    try { return Files.readString(f).replaceAll("\\s", "").length(); }
                                    catch (IOException e) { return 0; }
                                }).sum();
                        } catch (IOException ignored) {}
                    }
                    info.put("total_words", totalWords);
                    
                    // 最后修改时间
                    try {
                        info.put("last_modified", Files.getLastModifiedTime(dir).toString());
                    } catch (IOException ignored) {}
                    
                    projects.add(info);
                });
            }
        } catch (IOException e) {
            return ResponseEntity.internalServerError()
                .body(List.of(Map.of("error", "读取项目目录失败: " + e.getMessage())));
        }
        return ResponseEntity.ok(projects);
    }

    /**
     * GET /api/projects/{name}
     * 获取单个项目详情
     */
    @GetMapping("/{name}")
    public ResponseEntity<Map<String, Object>> getProject(@PathVariable String name) {
        Path projectDir = projectsRoot.resolve(name);
        if (!Files.exists(projectDir)) {
            return ResponseEntity.notFound().build();
        }

        Map<String, Object> info = new LinkedHashMap<>();
        info.put("name", name);
        
        // 章节列表
        Path bodyDir = projectDir.resolve("正文");
        List<Map<String, Object>> chapters = new ArrayList<>();
        if (Files.exists(bodyDir)) {
            try (Stream<Path> files = Files.list(bodyDir).sorted()) {
                files.filter(f -> f.toString().endsWith(".txt")).forEach(f -> {
                    Map<String, Object> ch = new LinkedHashMap<>();
                    ch.put("filename", f.getFileName().toString());
                    try {
                        String content = Files.readString(f);
                        ch.put("word_count", content.replaceAll("\\s", "").length());
                        ch.put("preview", content.length() > 200 ? content.substring(0, 200) + "..." : content);
                    } catch (IOException ignored) {}
                    chapters.add(ch);
                });
            } catch (IOException ignored) {}
        }
        info.put("chapters", chapters);
        info.put("chapter_count", chapters.size());

        return ResponseEntity.ok(info);
    }

    /**
     * POST /api/projects
     * 创建新项目
     */
    @PostMapping
    public ResponseEntity<Map<String, Object>> createProject(@RequestBody Map<String, String> request) {
        String name = request.get("name");
        if (name == null || name.isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "项目名不能为空"));
        }

        Path projectDir = projectsRoot.resolve(name);
        if (Files.exists(projectDir)) {
            return ResponseEntity.badRequest().body(Map.of("error", "项目已存在"));
        }

        try {
            Files.createDirectories(projectDir);
            Files.createDirectories(projectDir.resolve("正文"));
            Files.createDirectories(projectDir.resolve("大纲"));
            
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("name", name);
            result.put("path", projectDir.toString());
            result.put("created", LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
            result.put("status", "created");
            
            return ResponseEntity.ok(result);
        } catch (IOException e) {
            return ResponseEntity.internalServerError()
                .body(Map.of("error", "创建项目失败: " + e.getMessage()));
        }
    }

    /**
     * GET /api/projects/{name}/chapters/{num}
     * 获取指定章节内容
     */
    @GetMapping("/{name}/chapters/{num}")
    public ResponseEntity<Map<String, Object>> getChapter(
            @PathVariable String name, @PathVariable int num) {
        Path projectDir = projectsRoot.resolve(name);
        Path bodyDir = projectDir.resolve("正文");
        
        if (!Files.exists(bodyDir)) {
            return ResponseEntity.notFound().build();
        }

        // 查找匹配的章节文件
        try (Stream<Path> files = Files.list(bodyDir)) {
            Optional<Path> chapterFile = files
                .filter(f -> f.getFileName().toString().matches("第" + num + "章.*\\.txt"))
                .findFirst();

            if (chapterFile.isPresent()) {
                String content = Files.readString(chapterFile.get());
                Map<String, Object> result = new LinkedHashMap<>();
                result.put("chapter_num", num);
                result.put("filename", chapterFile.get().getFileName().toString());
                result.put("content", content);
                result.put("word_count", content.replaceAll("\\s", "").length());
                return ResponseEntity.ok(result);
            }
        } catch (IOException ignored) {}

        return ResponseEntity.notFound().build();
    }

    /**
     * PUT /api/projects/{name}/chapters/{num}
     * 保存/更新章节内容
     */
    @PutMapping("/{name}/chapters/{num}")
    public ResponseEntity<Map<String, Object>> saveChapter(
            @PathVariable String name, @PathVariable int num,
            @RequestBody Map<String, String> request) {
        
        String content = request.get("content");
        if (content == null || content.isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "内容不能为空"));
        }

        Path projectDir = projectsRoot.resolve(name);
        if (!Files.exists(projectDir)) {
            return ResponseEntity.notFound().build();
        }

        Path bodyDir = projectDir.resolve("正文");
        try {
            Files.createDirectories(bodyDir);
            Path chapterFile = bodyDir.resolve("第" + num + "章.txt");
            Files.writeString(chapterFile, content);

            Map<String, Object> result = new LinkedHashMap<>();
            result.put("chapter_num", num);
            result.put("path", chapterFile.toString());
            result.put("word_count", content.replaceAll("\\s", "").length());
            result.put("status", "saved");

            return ResponseEntity.ok(result);
        } catch (IOException e) {
            return ResponseEntity.internalServerError()
                .body(Map.of("error", "保存失败: " + e.getMessage()));
        }
    }
}
