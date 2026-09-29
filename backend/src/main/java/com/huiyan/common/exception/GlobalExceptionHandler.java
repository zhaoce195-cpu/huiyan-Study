package com.huiyan.common.exception;

import cn.dev33.satoken.exception.NotLoginException;
import cn.dev33.satoken.exception.NotPermissionException;
import cn.dev33.satoken.exception.NotRoleException;
import com.huiyan.common.response.R;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.BindException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.multipart.MaxUploadSizeExceededException;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<R<Object>> handleBusinessException(BusinessException e) {
        log.warn("业务异常: code={}, msg={}", e.getCode(), e.getMessage());
        HttpStatus status = HttpStatus.OK;
        if (e.getCode() == 401) {
            status = HttpStatus.UNAUTHORIZED;
        } else if (e.getCode() == 403) {
            status = HttpStatus.FORBIDDEN;
        } else if (e.getCode() == 404) {
            status = HttpStatus.NOT_FOUND;
        } else if (e.getCode() == 409) {
            status = HttpStatus.CONFLICT;
        }
        return ResponseEntity.status(status).body(R.fail(e.getCode(), e.getMessage(), e.getData()));
    }

    @ExceptionHandler(NotLoginException.class)
    public ResponseEntity<R<Object>> handleNotLoginException(NotLoginException e) {
        log.warn("未登录或令牌已失效: {}", e.getMessage());
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                .body(R.fail(R.CODE_UNAUTHORIZED, "未登录或登录已失效"));
    }

    @ExceptionHandler({NotRoleException.class, NotPermissionException.class})
    public ResponseEntity<R<Object>> handleForbiddenException(Exception e) {
        log.warn("权限不足: {}", e.getMessage());
        return ResponseEntity.status(HttpStatus.FORBIDDEN)
                .body(R.fail(R.CODE_FORBIDDEN, "当前账号角色无权访问，请联系管理员"));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<R<Object>> handleValidationException(MethodArgumentNotValidException e) {
        FieldError fieldError = e.getBindingResult().getFieldError();
        String msg = fieldError != null ? (fieldError.getField() + ": " + fieldError.getDefaultMessage()) : "参数校验失败";
        return ResponseEntity.ok(R.fail(R.CODE_VALIDATION, msg));
    }

    @ExceptionHandler(BindException.class)
    public ResponseEntity<R<Object>> handleBindException(BindException e) {
        FieldError fieldError = e.getBindingResult().getFieldError();
        String msg = fieldError != null ? (fieldError.getField() + ": " + fieldError.getDefaultMessage()) : "参数绑定失败";
        return ResponseEntity.ok(R.fail(R.CODE_VALIDATION, msg));
    }

    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public ResponseEntity<R<Object>> handleMaxUploadSizeExceededException(MaxUploadSizeExceededException e) {
        return ResponseEntity.ok(R.fail(R.CODE_BAD_REQUEST, "上传文件超过允许的最大体积限制"));
    }

    @ExceptionHandler(org.springframework.web.servlet.resource.NoResourceFoundException.class)
    public Object handleNoResourceFoundException(org.springframework.web.servlet.resource.NoResourceFoundException e, jakarta.servlet.http.HttpServletRequest request) {
        String path = request.getRequestURI();
        if (!path.startsWith("/api") && !path.startsWith("/static")) {
            return new org.springframework.web.servlet.ModelAndView("forward:/index.html");
        }
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(R.fail(404, "资源不存在: " + path));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<R<Object>> handleException(Exception e) {
        log.error("未捕获异常: ", e);
        return ResponseEntity.ok(R.fail(R.CODE_INTERNAL, "服务器内部错误：" + e.getMessage()));
    }
}
