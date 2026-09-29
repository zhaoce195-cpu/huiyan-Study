package com.huiyan.common.response;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.util.Collections;
import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PageResult<T> implements Serializable {

    private static final long serialVersionUID = 1L;

    private long total;
    private long page;
    private long pageSize;
    @Builder.Default
    private List<T> list = Collections.emptyList();

    @JsonProperty("page_size")
    public long getPageSizeSnake() {
        return pageSize;
    }

    public static <T> PageResult<T> of(long total, long page, long pageSize, List<T> list) {
        return PageResult.<T>builder()
                .total(total)
                .page(page)
                .pageSize(pageSize)
                .list(list != null ? list : Collections.emptyList())
                .build();
    }
}
