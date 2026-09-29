package com.huiyan.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.huiyan.common.exception.BusinessException;
import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.dto.common.CommonDTO;
import com.huiyan.entity.Notice;
import com.huiyan.entity.NoticeRead;
import com.huiyan.entity.User;
import com.huiyan.mapper.NoticeMapper;
import com.huiyan.mapper.NoticeReadMapper;
import com.huiyan.mapper.UserMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.*;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class NoticeService {

    private final NoticeMapper noticeMapper;
    private final NoticeReadMapper noticeReadMapper;
    private final UserMapper userMapper;

    public PageResult<Notice> getNotices(
            long page, long pageSize, String noticeType, String status, String keyword, Integer currentUserId
    ) {
        LambdaQueryWrapper<Notice> query = new LambdaQueryWrapper<>();
        if (noticeType != null && !noticeType.trim().isEmpty()) {
            query.eq(Notice::getNoticeType, noticeType.trim());
        }
        if (status != null && !status.trim().isEmpty()) {
            query.eq(Notice::getStatus, status.trim());
        }
        if (keyword != null && !keyword.trim().isEmpty()) {
            query.and(q -> q.like(Notice::getTitle, keyword.trim()).or().like(Notice::getSummary, keyword.trim()));
        }
        query.orderByDesc(Notice::getIsTop).orderByDesc(Notice::getCreatedAt);

        Page<Notice> pageParam = new Page<>(page, pageSize);
        Page<Notice> result = noticeMapper.selectPage(pageParam, query);

        Set<Integer> readNoticeIds = Collections.emptySet();
        if (currentUserId != null) {
            List<NoticeRead> reads = noticeReadMapper.selectList(new LambdaQueryWrapper<NoticeRead>()
                    .eq(NoticeRead::getUserId, currentUserId));
            readNoticeIds = reads.stream().map(NoticeRead::getNoticeId).collect(Collectors.toSet());
        }

        List<User> publishers = userMapper.selectList(null);
        Map<Integer, String> userMap = publishers.stream().collect(Collectors.toMap(User::getId, u -> u.getRealName() != null && !u.getRealName().isEmpty() ? u.getRealName() : u.getUsername(), (a, b) -> a));

        for (Notice n : result.getRecords()) {
            n.setPublisherName(userMap.get(n.getPublisherId()));
            n.setIsRead(readNoticeIds.contains(n.getId()));
        }

        return PageResult.of(result.getTotal(), page, pageSize, result.getRecords());
    }

    public Notice getNoticeDetail(Integer id, Integer currentUserId) {
        Notice notice = noticeMapper.selectById(id);
        if (notice == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "公告不存在");
        }
        notice.setViewCount((notice.getViewCount() != null ? notice.getViewCount() : 0) + 1);
        noticeMapper.updateById(notice);

        if (currentUserId != null) {
            markRead(currentUserId, id);
            notice.setIsRead(true);
        }
        User publisher = userMapper.selectById(notice.getPublisherId());
        if (publisher != null) {
            notice.setPublisherName(publisher.getRealName() != null ? publisher.getRealName() : publisher.getUsername());
        }
        return notice;
    }

    @Transactional
    public Notice saveNotice(CommonDTO.NoticeSaveRequest req, Integer publisherId) {
        if (req.getTitle() == null || req.getTitle().trim().isEmpty()) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "公告标题不能为空");
        }
        Notice notice = Notice.builder()
                .title(req.getTitle().trim())
                .summary(req.getSummary() != null ? req.getSummary() : "")
                .content(req.getContent() != null ? req.getContent() : "")
                .coverUrl(req.getCoverUrl() != null ? req.getCoverUrl() : "")
                .noticeType(req.getNoticeType() != null ? req.getNoticeType() : "SYSTEM")
                .status(req.getStatus() != null ? req.getStatus() : "PUBLISHED")
                .visibleRoles(req.getVisibleRoles() != null ? req.getVisibleRoles() : "")
                .isTop(Boolean.TRUE.equals(req.getIsTop()))
                .publisherId(publisherId)
                .publishAt(req.getPublishAt() != null ? req.getPublishAt() : LocalDateTime.now())
                .expireAt(req.getExpireAt())
                .viewCount(0)
                .build();
        notice.setCreatedAt(LocalDateTime.now());
        notice.setUpdatedAt(LocalDateTime.now());
        noticeMapper.insert(notice);
        return notice;
    }

    @Transactional
    public void updateNotice(Integer id, CommonDTO.NoticeSaveRequest req) {
        Notice notice = noticeMapper.selectById(id);
        if (notice == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "公告不存在");
        }
        if (req.getTitle() != null) notice.setTitle(req.getTitle());
        if (req.getSummary() != null) notice.setSummary(req.getSummary());
        if (req.getContent() != null) notice.setContent(req.getContent());
        if (req.getCoverUrl() != null) notice.setCoverUrl(req.getCoverUrl());
        if (req.getNoticeType() != null) notice.setNoticeType(req.getNoticeType());
        if (req.getStatus() != null) notice.setStatus(req.getStatus());
        if (req.getVisibleRoles() != null) notice.setVisibleRoles(req.getVisibleRoles());
        if (req.getIsTop() != null) notice.setIsTop(req.getIsTop());
        if (req.getPublishAt() != null) notice.setPublishAt(req.getPublishAt());
        if (req.getExpireAt() != null) notice.setExpireAt(req.getExpireAt());
        notice.setUpdatedAt(LocalDateTime.now());
        noticeMapper.updateById(notice);
    }

    @Transactional
    public void deleteNotice(Integer id) {
        noticeMapper.deleteById(id);
    }

    @Transactional
    public void markRead(Integer userId, Integer noticeId) {
        NoticeRead existing = noticeReadMapper.selectOne(new LambdaQueryWrapper<NoticeRead>()
                .eq(NoticeRead::getUserId, userId)
                .eq(NoticeRead::getNoticeId, noticeId));
        if (existing == null) {
            NoticeRead read = NoticeRead.builder()
                    .userId(userId)
                    .noticeId(noticeId)
                    .build();
            read.setCreatedAt(LocalDateTime.now());
            read.setUpdatedAt(LocalDateTime.now());
            noticeReadMapper.insert(read);
        }
    }

    @Transactional
    public void markAllRead(Integer userId) {
        List<Notice> notices = noticeMapper.selectList(new LambdaQueryWrapper<Notice>()
                .eq(Notice::getStatus, "PUBLISHED"));
        for (Notice n : notices) {
            markRead(userId, n.getId());
        }
    }
}
