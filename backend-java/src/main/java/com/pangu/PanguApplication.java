package com.pangu;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

/**
 * 盘古AI后端骨架 — 入口
 * 
 * Java = 骨架：稳定的API路由、连接池管理、任务队列、事务控制
 * Python = 血液：数学引擎、AI生成、NLP分析
 * REST API = 血管：连接骨架与血液
 */
@SpringBootApplication
@ConfigurationPropertiesScan
public class PanguApplication {
    public static void main(String[] args) {
        SpringApplication.run(PanguApplication.class, args);
        System.out.println("========================================");
        System.out.println("  盘古AI后端骨架已启动 (Java 21 + Spring Boot 3.2)");
        System.out.println("  API文档: http://localhost:8080/actuator/health");
        System.out.println("  Python血液层: http://localhost:5000 (需单独启动)");
        System.out.println("========================================");
    }
}
