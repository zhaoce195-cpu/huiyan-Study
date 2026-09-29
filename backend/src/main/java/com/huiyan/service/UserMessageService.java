package com.huiyan.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.huiyan.common.exception.BusinessException;
import com.huiyan.common.response.R;
import com.huiyan.dto.message.UserMessageDTO;
import com.huiyan.entity.UserMessage;
import com.huiyan.mapper.UserMessageMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class UserMessageService {

    private final UserMessageMapper userMessageMapper;

    @Transactional
    public UserMessage push(
            Integer userId,
            String msgType,
            String title,
            String content,
            String refType,
            Integer refId
    ) {
        UserMessage msg = UserMessage.builder()
                .userId(userId)
                .type(msgType)
                .title(title != null ? title : "")
                .content(content != null ? content : "")
                .refType(refType != null ? refType : "")
                .refId(refId)
                .isRead(false)
                .build();
        msg.setCreatedAt(LocalDateTime.now());
        userMessageMapper.insert(msg);
        return msg;
    }

    public UserMessageDTO.MessagePage listMy(
            Integer userId,
            String msgType,
            long page,
            long pageSize
    ) {
        LambdaQueryWrapper<UserMessage> query = new LambdaQueryWrapper<>();
        query.eq(UserMessage::getUserId, userId);
        if (msgType != null && !msgType.trim().isEmpty()) {
            query.eq(UserMessage::getType, msgType.trim());
        }
        query.orderByDesc(UserMessage::getId);

        Page<UserMessage> pageParam = new Page<>(Math.max(1, page), Math.max(1, Math.min(100, pageSize)));
        Page<UserMessage> result = userMessageMapper.selectPage(pageParam, query);

        Long unread = userMessageMapper.selectCount(new LambdaQueryWrapper<UserMessage>()
                .eq(UserMessage::getUserId, userId)
                .eq(UserMessage::getIsRead, false));

        return UserMessageDTO.MessagePage.builder()
                .total(result.getTotal())
                .unread(unread != null ? unread : 0)
                .page(page)
                .pageSize(pageSize)
                .list(result.getRecords())
                .build();
    }

    public long unreadCount(Integer userId) {
        Long unread = userMessageMapper.selectCount(new LambdaQueryWrapper<UserMessage>()
                .eq(UserMessage::getUserId, userId)
                .eq(UserMessage::getIsRead, false));
        return unread != null ? unread : 0;
    }

    @Transactional
    public int markRead(Integer userId, List<Integer> ids) {
        if (ids == null || ids.isEmpty()) return 0;

        List<UserMessage> messages = userMessageMapper.selectList(new LambdaQueryWrapper<UserMessage>()
                .eq(UserMessage::getUserId, userId)
                .in(UserMessage::getId, ids)
                .eq(UserMessage::getIsRead, false));

        LocalDateTime now = LocalDateTime.now();
        for (UserMessage m : messages) {
            m.setIsRead(true);
            m.setReadAt(now);
            userMessageMapper.updateById(m);
        }
        return messages.size();
    }

    @Transactional
    public int markAllRead(Integer userId) {
        List<UserMessage> messages = userMessageMapper.selectList(new LambdaQueryWrapper<UserMessage>()
                .eq(UserMessage::getUserId, userId)
                .eq(UserMessage::getIsRead, false));

        LocalDateTime now = LocalDateTime.now();
        for (UserMessage m : messages) {
            m.setIsRead(true);
            m.setReadAt(now);
            userMessageMapper.updateById(m);
        }
        return messages.size();
    }

    public UserMessage assertOwner(Integer userId, Integer msgId) {
        UserMessage msg = userMessageMapper.selectById(msgId);
        if (msg == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "消息不存在：" + msgId);
        }
        if (!userId.equals(msg.getUserId())) {
            throw new BusinessException(R.CODE_FORBIDDEN, "无权操作他人消息");
        }
        return msg;
    }
}
