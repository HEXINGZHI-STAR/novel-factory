package com.pangu.controller;

import com.pangu.service.PythonBridge;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.*;
import java.util.concurrent.CompletableFuture;

/**
 * 数学分析API — 血液层的入口
 * 
 * 前端/其他服务通过此Controller调用Python数学引擎。
 * 这是"血管"的Java端接口。
 */
@RestController
@RequestMapping("/api/analysis")
@CrossOrigin(origins = "*")
public class AnalysisController {

    private static final Logger log = LoggerFactory.getLogger(AnalysisController.class);
    private final PythonBridge bridge;

    public AnalysisController(PythonBridge bridge) {
        this.bridge = bridge;
    }

    /**
     * POST /api/analysis/chapter
     * 对单个章节文本进行完整数学分析（线性代数+傅里叶+拉普拉斯+积分+马尔可夫+信息论）
     */
    @PostMapping("/chapter")
    public CompletableFuture<ResponseEntity<Map<String, Object>>> analyzeChapter(
            @RequestBody Map<String, Object> request) {

        String text = (String) request.getOrDefault("text", "");
        int chapterNum = request.containsKey("chapter_num") 
            ? ((Number) request.get("chapter_num")).intValue() : 1;

        if (text.length() < 200) {
            return CompletableFuture.completedFuture(
                ResponseEntity.badRequest().body(Map.of("error", "文本过短，至少200字"))
            );
        }

        return bridge.analyzeChapter(text, chapterNum)
            .thenApply(ResponseEntity::ok);
    }

    /**
     * POST /api/analysis/compare
     * 对比两个章节
     */
    @PostMapping("/compare")
    public CompletableFuture<ResponseEntity<Map<String, Object>>> compareChapters(
            @RequestBody Map<String, String> request) {

        String text1 = request.getOrDefault("text1", "");
        String text2 = request.getOrDefault("text2", "");

        return bridge.compareChapters(text1, text2)
            .thenApply(ResponseEntity::ok);
    }

    /**
     * POST /api/analysis/sequence
     * 多章序列分析
     */
    @PostMapping("/sequence")
    public CompletableFuture<ResponseEntity<Map<String, Object>>> analyzeSequence(
            @RequestBody Map<String, Object> request) {

        @SuppressWarnings("unchecked")
        List<String> chapters = (List<String>) request.getOrDefault("chapters", List.of());

        if (chapters.size() < 2) {
            return CompletableFuture.completedFuture(
                ResponseEntity.badRequest().body(Map.of("error", "至少需要2章"))
            );
        }

        return bridge.analyzeSequence(chapters)
            .thenApply(ResponseEntity::ok);
    }

    /**
     * POST /api/analysis/guidance
     * 获取写作优化指引（基于分析结果）
     */
    @PostMapping("/guidance")
    public ResponseEntity<Map<String, Object>> getGuidance(
            @RequestBody Map<String, Object> request) {

        @SuppressWarnings("unchecked")
        Map<String, Object> analysisResult = (Map<String, Object>) 
            request.getOrDefault("analysis_result", Map.of());
        String platform = (String) request.getOrDefault("platform", "qimao");

        String guidance = bridge.getGuidancePrompt(analysisResult, platform);
        return ResponseEntity.ok(Map.of(
            "platform", platform,
            "guidance", guidance
        ));
    }

    /**
     * GET /api/analysis/health
     * Python引擎健康检查
     */
    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> healthCheck() {
        Map<String, Object> health = bridge.healthCheck();
        return ResponseEntity.ok(health);
    }
}
