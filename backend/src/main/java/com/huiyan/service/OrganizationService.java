package com.huiyan.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.huiyan.common.exception.BusinessException;
import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.entity.Organization;
import com.huiyan.entity.OrganizationApplication;
import com.huiyan.entity.User;
import com.huiyan.mapper.OrganizationApplicationMapper;
import com.huiyan.mapper.OrganizationMapper;
import com.huiyan.mapper.UserMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.*;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class OrganizationService {

    private final OrganizationMapper organizationMapper;
    private final OrganizationApplicationMapper organizationApplicationMapper;
    private final UserMapper userMapper;
    private final UserMessageService userMessageService;

    public List<Organization> listOrgs(String keyword) {
        LambdaQueryWrapper<Organization> query = new LambdaQueryWrapper<>();
        query.eq(Organization::getIsActive, true);
        if (keyword != null && !keyword.trim().isEmpty()) {
            String kw = keyword.trim();
            query.and(q -> q.like(Organization::getName, kw).or().like(Organization::getCode, kw));
        }
        query.orderByAsc(Organization::getId);
        return organizationMapper.selectList(query);
    }

    @Transactional
    public OrganizationApplication apply(Integer organizationId, String reason, User user) {
        Organization org = organizationMapper.selectById(organizationId);
        if (org == null || Boolean.FALSE.equals(org.getIsActive())) {
            throw new BusinessException(R.CODE_NOT_FOUND, "机构不存在或已停用");
        }

        Long pendingCount = organizationApplicationMapper.selectCount(new LambdaQueryWrapper<OrganizationApplication>()
                .eq(OrganizationApplication::getApplicantId, user.getId())
                .eq(OrganizationApplication::getOrganizationId, organizationId)
                .eq(OrganizationApplication::getStatus, "PENDING"));
        if (pendingCount != null && pendingCount > 0) {
            throw new BusinessException(R.CODE_CONFLICT, "该机构已存在待审核的申请，请耐心等待审核结果");
        }

        OrganizationApplication app = OrganizationApplication.builder()
                .applicantId(user.getId())
                .organizationId(organizationId)
                .reason(reason != null ? reason.trim() : "")
                .status("PENDING")
                .build();
        app.setCreatedAt(LocalDateTime.now());
        app.setUpdatedAt(LocalDateTime.now());
        organizationApplicationMapper.insert(app);

        populateMetadata(List.of(app));
        return app;
    }

    public PageResult<OrganizationApplication> listMyApplications(long page, long pageSize, User user) {
        LambdaQueryWrapper<OrganizationApplication> query = new LambdaQueryWrapper<>();
        query.eq(OrganizationApplication::getApplicantId, user.getId());
        query.orderByDesc(OrganizationApplication::getId);

        Page<OrganizationApplication> pageParam = new Page<>(Math.max(1, page), Math.max(1, Math.min(100, pageSize)));
        Page<OrganizationApplication> result = organizationApplicationMapper.selectPage(pageParam, query);

        populateMetadata(result.getRecords());
        return PageResult.of(result.getTotal(), page, pageSize, result.getRecords());
    }

    public PageResult<OrganizationApplication> listForAdmin(
            long page, long pageSize, String keyword, String status, Integer organizationId
    ) {
        LambdaQueryWrapper<OrganizationApplication> query = new LambdaQueryWrapper<>();
        if (status != null && !status.trim().isEmpty()) {
            query.eq(OrganizationApplication::getStatus, status.trim());
        }
        if (organizationId != null) {
            query.eq(OrganizationApplication::getOrganizationId, organizationId);
        }

        if (keyword != null && !keyword.trim().isEmpty()) {
            String kw = keyword.trim();
            List<User> matchedUsers = userMapper.selectList(new LambdaQueryWrapper<User>()
                    .like(User::getRealName, kw)
                    .or().like(User::getUsername, kw)
                    .or().like(User::getPhone, kw));
            Set<Integer> userIds = matchedUsers.stream().map(User::getId).collect(Collectors.toSet());

            List<Organization> matchedOrgs = organizationMapper.selectList(new LambdaQueryWrapper<Organization>()
                    .like(Organization::getName, kw));
            Set<Integer> orgIds = matchedOrgs.stream().map(Organization::getId).collect(Collectors.toSet());

            query.and(q -> {
                q.like(OrganizationApplication::getReason, kw);
                if (!userIds.isEmpty()) {
                    q.or().in(OrganizationApplication::getApplicantId, userIds);
                }
                if (!orgIds.isEmpty()) {
                    q.or().in(OrganizationApplication::getOrganizationId, orgIds);
                }
            });
        }

        query.orderByDesc(OrganizationApplication::getId);

        Page<OrganizationApplication> pageParam = new Page<>(Math.max(1, page), Math.max(1, Math.min(100, pageSize)));
        Page<OrganizationApplication> result = organizationApplicationMapper.selectPage(pageParam, query);

        populateMetadata(result.getRecords());
        return PageResult.of(result.getTotal(), page, pageSize, result.getRecords());
    }

    @Transactional
    public OrganizationApplication review(Integer appId, boolean accept, String comment, User reviewer) {
        OrganizationApplication app = organizationApplicationMapper.selectById(appId);
        if (app == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "申请不存在：" + appId);
        }
        if (!"PENDING".equalsIgnoreCase(app.getStatus())) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "申请已审核（" + app.getStatus() + "），无法再次操作");
        }

        String c = comment != null ? comment.trim() : "";
        if (!accept && c.isEmpty()) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "驳回时必须填写驳回理由");
        }

        Organization org = organizationMapper.selectById(app.getOrganizationId());
        String orgName = org != null ? org.getName() : ("机构#" + app.getOrganizationId());

        LocalDateTime now = LocalDateTime.now();
        app.setReviewerId(reviewer.getId());
        app.setReviewedAt(now);
        app.setReviewComment(c);

        if (accept) {
            app.setStatus("APPROVED");
            User applicant = userMapper.selectById(app.getApplicantId());
            if (applicant != null) {
                applicant.setDepartment(orgName);
                applicant.setUpdatedAt(now);
                userMapper.updateById(applicant);
            }

            String msgContent = "您申请加入「" + orgName + "」的请求已通过审核。" + (!c.isEmpty() ? "\n审核备注：" + c : "");
            userMessageService.push(app.getApplicantId(), "org_application", "机构申请已通过", msgContent, "org_application", app.getId());
        } else {
            app.setStatus("REJECTED");
            String msgContent = "您申请加入「" + orgName + "」的请求未通过审核。\n驳回理由：" + c;
            userMessageService.push(app.getApplicantId(), "org_application", "机构申请未通过", msgContent, "org_application", app.getId());
        }

        app.setUpdatedAt(now);
        organizationApplicationMapper.updateById(app);

        populateMetadata(List.of(app));
        return app;
    }

    private void populateMetadata(List<OrganizationApplication> list) {
        if (list == null || list.isEmpty()) return;

        Set<Integer> userIds = new HashSet<>();
        Set<Integer> orgIds = new HashSet<>();
        for (OrganizationApplication a : list) {
            if (a.getApplicantId() != null) userIds.add(a.getApplicantId());
            if (a.getReviewerId() != null) userIds.add(a.getReviewerId());
            if (a.getOrganizationId() != null) orgIds.add(a.getOrganizationId());
        }

        Map<Integer, User> userMap = new HashMap<>();
        if (!userIds.isEmpty()) {
            List<User> users = userMapper.selectBatchIds(userIds);
            for (User u : users) {
                userMap.put(u.getId(), u);
            }
        }

        Map<Integer, Organization> orgMap = new HashMap<>();
        if (!orgIds.isEmpty()) {
            List<Organization> orgs = organizationMapper.selectBatchIds(orgIds);
            for (Organization o : orgs) {
                orgMap.put(o.getId(), o);
            }
        }

        for (OrganizationApplication a : list) {
            User applicant = userMap.get(a.getApplicantId());
            if (applicant != null) {
                a.setApplicantName(applicant.getRealName() != null && !applicant.getRealName().isEmpty() ? applicant.getRealName() : applicant.getUsername());
                a.setApplicantPhone(applicant.getPhone() != null ? applicant.getPhone() : "");
            }
            User reviewer = userMap.get(a.getReviewerId());
            if (reviewer != null) {
                a.setReviewerName(reviewer.getRealName() != null && !reviewer.getRealName().isEmpty() ? reviewer.getRealName() : reviewer.getUsername());
            }
            Organization org = orgMap.get(a.getOrganizationId());
            if (org != null) {
                a.setOrganizationName(org.getName());
            }
        }
    }
}
