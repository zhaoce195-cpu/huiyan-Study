package com.huiyan.dto.message;

import com.huiyan.entity.UserMessage;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

public class UserMessageDTO {

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class MessagePage {
        private long total;
        private long unread;
        private long page;
        private long pageSize;
        private List<UserMessage> list;
    }
}
