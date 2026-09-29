package com.huiyan.common.response;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonInclude(JsonInclude.Include.ALWAYS)
public class R<T> implements Serializable {

    private static final long serialVersionUID = 1L;

    public static final int CODE_OK = 0;
    public static final int CODE_BAD_REQUEST = 400;
    public static final int CODE_UNAUTHORIZED = 401;
    public static final int CODE_FORBIDDEN = 403;
    public static final int CODE_NOT_FOUND = 404;
    public static final int CODE_CONFLICT = 409;
    public static final int CODE_VALIDATION = 422;
    public static final int CODE_INTERNAL = 500;

    private int code;
    private String msg;
    private T data;

    public static <T> R<T> ok() {
        return ok(null, "success");
    }

    public static <T> R<T> ok(T data) {
        return ok(data, "success");
    }

    public static <T> R<T> ok(T data, String msg) {
        return R.<T>builder()
                .code(CODE_OK)
                .msg(msg != null ? msg : "success")
                .data(data)
                .build();
    }

    public static <T> R<T> fail(String msg) {
        return fail(CODE_BAD_REQUEST, msg, null);
    }

    public static <T> R<T> fail(int code, String msg) {
        return fail(code, msg, null);
    }

    public static <T> R<T> fail(int code, String msg, T data) {
        return R.<T>builder()
                .code(code)
                .msg(msg)
                .data(data)
                .build();
    }
}
