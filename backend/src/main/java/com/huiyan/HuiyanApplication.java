package com.huiyan;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@MapperScan("com.huiyan.mapper")
public class HuiyanApplication {

    public static void main(String[] args) {
        SpringApplication.run(HuiyanApplication.class, args);
    }
}
