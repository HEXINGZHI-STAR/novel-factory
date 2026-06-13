package com.pangu.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.CompletableFuture;

/**
 * Python 血液层桥接器 (HTTP版)
 *
 * 骨架(Java)通过 HTTP 调用血液(Python)的盘古引擎。
 * 替代旧的 ProcessBuilder 方式，性能提升 10-100x。
 *
 * Python 服务启动: python pangu_bridge.py --port 5100
 */
@Service
public class PythonBridge {

    private static final Logger log = LoggerFactory.getLogger(PythonBridge.class);
    private final ObjectMapper mapper = new ObjectMapper();
    private final HttpClient client;
    private final String baseUrl;

    public PythonBridge(@Value("${pangu.python.bridge.url:http://127.0.0.1:5100}") String baseUrl) {
        this.baseUrl = baseUrl;
        this.client = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(10))
                .build();
        log.info("PythonBridge 初始化: {}", baseUrl);
    }

    // ================================================================
    // 核心写作
    // ================================================================

    /**
     * 写一章 (完整 Pipeline W0-W5)
     */
    public CompletableFuture<Map<String, Object>> writeChapter(
            String project, int chapter, String task, String mode, String platform) {
        return post("/write", Map.of(
                "project", project,
                "chapter", chapter,
                "task", task != null ? task : "",
                "mode", mode != null ? mode : "workshop",
                "platform", platform != null ? platform : "qimao"
        ));
    }

    /**
     * 审查章节 (全维度情报分析)
     */
    public CompletableFuture<Map<String, Object>> reviewChapter(
            String project, int chapter) {
        return post("/review", Map.of(
                "project", project,
                "chapter", chapter
        ));
    }

    // ================================================================
    // 数学引擎
    // ================================================================

    /**
     * 文本统计: 句均/CV/长句比/对话率/AI风险
     */
    public CompletableFuture<Map<String, Object>> analyzeStats(String text) {
        return post("/analyze/stats", Map.of("text", text));
    }

    /**
     * 情感弧线: 匹配6种经典弧线, 推荐下一章方向
     */
    public CompletableFuture<Map<String, Object>> analyzeEmotionalArc(
            List<Double> chapterValences, String expectedArc) {
        return post("/analyze/arc", Map.of(
                "valences", chapterValences,
                "expected_arc", expectedArc != null ? expectedArc : ""
        ));
    }

    /**
     * 说服力分析: AIDA漏斗 + 好奇心缺口 + 蔡格尼克效应
     */
    public CompletableFuture<Map<String, Object>> analyzePersuasion(String text) {
        return post("/analyze/persuasion", Map.of("text", text));
    }

    /**
     * 神经共鸣: 镜像/催产素/杏仁核/五感脑区激活
     */
    public CompletableFuture<Map<String, Object>> analyzeNeuralResonance(String text) {
        return post("/analyze/neural", Map.of("text", text));
    }

    /**
     * 认知负荷: 工作记忆/悬念超载/弃书预测
     */
    public CompletableFuture<Map<String, Object>> analyzeCognitiveLoad(
            String text, List<String> knownChars, int knownForeshadowing) {
        return post("/analyze/cognitive", Map.of(
                "text", text,
                "known_characters", knownChars != null ? knownChars : List.of(),
                "foreshadowing_count", knownForeshadowing
        ));
    }

    // ================================================================
    // 策略 & 趋势
    // ================================================================

    /**
     * 获取写作策略: 模式/字数/温度/钩子/释放
     */
    public CompletableFuture<Map<String, Object>> getStrategy(
            String project, int chapter) {
        return post("/strategy", Map.of(
                "project", project,
                "chapter", chapter
        ));
    }

    /**
     * 趋势雷达: 推荐最佳入场题材
     */
    public CompletableFuture<Map<String, Object>> trendRadar(String platform) {
        return post("/trend/radar", Map.of("platform", platform));
    }

    // ================================================================
    // 项目管理
    // ================================================================

    /**
     * 列出所有项目
     */
    public CompletableFuture<List<Map<String, Object>>> listProjects() {
        return get("/projects");
    }

    /**
     * 创建项目
     */
    public CompletableFuture<Map<String, Object>> createProject(
            String title, String platform, String genre, int chapters) {
        return post("/projects/create", Map.of(
                "title", title,
                "platform", platform,
                "genre", genre,
                "chapters", chapters
        ));
    }

    /**
     * 健康检查
     */
    public CompletableFuture<Map<String, Object>> healthCheck() {
        return get("/health");
    }

    // ================================================================
    // HTTP 工具
    // ================================================================

    @SuppressWarnings("unchecked")
    private CompletableFuture<Map<String, Object>> post(String path, Map<String, Object> body) {
        return CompletableFuture.supplyAsync(() -> {
            try {
                String json = mapper.writeValueAsString(body);
                HttpRequest request = HttpRequest.newBuilder()
                        .uri(URI.create(baseUrl + path))
                        .header("Content-Type", "application/json")
                        .POST(HttpRequest.BodyPublishers.ofString(json))
                        .timeout(Duration.ofSeconds(120))
                        .build();

                HttpResponse<String> response = client.send(request,
                        HttpResponse.BodyHandlers.ofString());

                if (response.statusCode() == 200) {
                    return mapper.readValue(response.body(), Map.class);
                }
                log.warn("PythonBridge {} 返回 {}", path, response.statusCode());
                return Map.of("error", "HTTP " + response.statusCode());
            } catch (Exception e) {
                log.error("PythonBridge {} 异常: {}", path, e.getMessage());
                return Map.of("error", e.getMessage());
            }
        });
    }

    @SuppressWarnings("unchecked")
    private CompletableFuture<List<Map<String, Object>>> get(String path) {
        return CompletableFuture.supplyAsync(() -> {
            try {
                HttpRequest request = HttpRequest.newBuilder()
                        .uri(URI.create(baseUrl + path))
                        .GET()
                        .timeout(Duration.ofSeconds(30))
                        .build();

                HttpResponse<String> response = client.send(request,
                        HttpResponse.BodyHandlers.ofString());

                if (response.statusCode() == 200) {
                    return mapper.readValue(response.body(), List.class);
                }
                return List.of();
            } catch (Exception e) {
                log.error("PythonBridge GET {} 异常: {}", path, e.getMessage());
                return List.of();
            }
        });
    }

    @SuppressWarnings("unchecked")
    private CompletableFuture<Map<String, Object>> get(String path) {
        return CompletableFuture.supplyAsync(() -> {
            try {
                HttpRequest request = HttpRequest.newBuilder()
                        .uri(URI.create(baseUrl + path))
                        .GET()
                        .timeout(Duration.ofSeconds(30))
                        .build();
                HttpResponse<String> response = client.send(request,
                        HttpResponse.BodyHandlers.ofString());
                if (response.statusCode() == 200) {
                    return mapper.readValue(response.body(), Map.class);
                }
                return Map.of("error", "HTTP " + response.statusCode());
            } catch (Exception e) {
                return Map.of("error", e.getMessage());
            }
        });
    }
}
