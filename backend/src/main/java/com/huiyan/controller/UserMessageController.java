package com.huiyan.controller;

import com.huiyan.common.response.R;
import com.huiyan.common.util.SecurityUtils;
import com.huiyan.dto.message.UserMessageDTO;
import com.huiyan.entity.User;
import com.huiyan.service.UserMessageService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Collections;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/user-messages")
@RequiredArgsConstructor
public class UserMessageController {

    private final UserMessageService userMessageService;

    @GetMapping("")
    public R<UserMessageDTO.MessagePage> listMyMessages(
            @RequestParam(required = false) String type,
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long pageSize
    ) {
        User user = SecurityUtils.getCurrentUser();
        return R.ok(userMessageService.listMy(user.getId(), type, page, pageSize));
    }

    @GetMapping("/unread-count")
    public R<Map<String, Object>> myUnreadCount() {
        User user = SecurityUtils.getCurrentUser();
        long unread = userMessageService.unreadCount(user.getId());
        return R.ok(Map.of("unread", unread));
    }

    @PostMapping("/{msgId}/read")
    public R<Void> markOneRead(@PathVariable Integer msgId) {
        User user = SecurityUtils.getCurrentUser();
        userMessageService.assertOwner(user.getId(), msgId);
        userMessageService.markRead(user.getId(), List.of(msgId));
        return R.ok(null, "已标记为已读");
    }

    @PostMapping("/read")
    public R<Map<String, Object>> markBatchRead(@RequestBody Map<String, Object> req) {
        User user = SecurityUtils.getCurrentUser();
        List<?> rawIds = (List<?>) req.getOrDefault("ids", Collections.emptyList());
        List<Integer> ids = rawIds.stream().map(o -> Integer.valueOf(o.toString())).toList();
        int updated = userMessageService.markRead(user.getId(), ids);
        return R.ok(Map.of("updated", updated));
    }

    @PostMapping("/read-all")
    public R<Map<String, Object>> markAllRead() {
        User user = SecurityUtils.getCurrentUser();
        int updated = userMessageService.markAllRead(user.getId());
        return R.ok(Map.of("updated", updated), "已全部标为已读");
    }
}
