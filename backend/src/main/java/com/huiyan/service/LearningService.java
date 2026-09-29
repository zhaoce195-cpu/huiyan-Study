package com.huiyan.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.huiyan.common.exception.BusinessException;
import com.huiyan.common.response.PageResult;
import com.huiyan.common.response.R;
import com.huiyan.entity.*;
import com.huiyan.mapper.*;
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
public class LearningService {

    private final LearningResourceMapper learningResourceMapper;
    private final ResourceFavoriteMapper resourceFavoriteMapper;
    private final LearningNoteMapper learningNoteMapper;
    private final TrainingCaseMapper trainingCaseMapper;
    private final UserMapper userMapper;
    private final RoleMapper roleMapper;

    private static final Map<String, String> TYPE_TEXT = Map.of(
            "CASE_TEMPLATE", "病例范本",
            "COURSEWARE", "实训课件",
            "KNOWLEDGE", "知识点文档",
            "IMAGE_DEMO", "教学影像"
    );

    private String getRoleCode(User user) {
        if (user == null || user.getRoleId() == null) return "STUDENT";
        Role role = roleMapper.selectById(user.getRoleId());
        return role != null ? role.getCode() : "STUDENT";
    }

    private boolean isTeacherOrAdmin(User user) {
        String role = getRoleCode(user);
        return "TEACHER".equalsIgnoreCase(role) || "ADMIN".equalsIgnoreCase(role);
    }

    private boolean isAdmin(User user) {
        return "ADMIN".equalsIgnoreCase(getRoleCode(user));
    }

    public PageResult<LearningResource> listResources(
            long page, long pageSize, String keyword, String resourceType, String status, Boolean onlyMine, User user
    ) {
        boolean teacher = isTeacherOrAdmin(user);
        LambdaQueryWrapper<LearningResource> query = new LambdaQueryWrapper<>();

        if (!teacher) {
            query.eq(LearningResource::getStatus, "PUBLISHED");
            // If caseId is not null, training case must be is_train_case == true
            // General resources without caseId must not be filtered out
            List<TrainingCase> nonTrainCases = trainingCaseMapper.selectList(
                    new LambdaQueryWrapper<TrainingCase>().eq(TrainingCase::getIsTrainCase, false)
            );
            if (!nonTrainCases.isEmpty()) {
                Set<Integer> nonTrainCaseIds = nonTrainCases.stream().map(TrainingCase::getId).collect(Collectors.toSet());
                query.and(q -> q.isNull(LearningResource::getCaseId).or().notIn(LearningResource::getCaseId, nonTrainCaseIds));
            }
        } else {
            if (status != null && !status.trim().isEmpty()) {
                query.eq(LearningResource::getStatus, status.trim());
            }
            if (Boolean.TRUE.equals(onlyMine) && user != null) {
                query.eq(LearningResource::getPublisherId, user.getId());
            }
        }

        if (keyword != null && !keyword.trim().isEmpty()) {
            String kw = keyword.trim();
            query.and(q -> q.like(LearningResource::getTitle, kw)
                    .or().like(LearningResource::getSummary, kw)
                    .or().like(LearningResource::getTags, kw));
        }

        if (resourceType != null && !resourceType.trim().isEmpty()) {
            query.eq(LearningResource::getResourceType, resourceType.trim());
        }

        query.orderByDesc(LearningResource::getId);

        Page<LearningResource> pageParam = new Page<>(Math.max(1, page), Math.max(1, Math.min(200, pageSize)));
        Page<LearningResource> result = learningResourceMapper.selectPage(pageParam, query);

        populateResourcesMetadata(result.getRecords(), user);

        return PageResult.of(result.getTotal(), page, pageSize, result.getRecords());
    }

    public LearningResource getResource(Integer id, User user) {
        LearningResource resource = learningResourceMapper.selectById(id);
        if (resource == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "资料不存在：" + id);
        }

        boolean teacher = isTeacherOrAdmin(user);
        if (!"PUBLISHED".equalsIgnoreCase(resource.getStatus()) && !teacher && (user == null || !Objects.equals(resource.getPublisherId(), user.getId()))) {
            throw new BusinessException(R.CODE_FORBIDDEN, "该资料未发布，无权查看");
        }

        if (!teacher && resource.getCaseId() != null) {
            TrainingCase tc = trainingCaseMapper.selectById(resource.getCaseId());
            if (tc == null || !Boolean.TRUE.equals(tc.getIsTrainCase())) {
                throw new BusinessException(R.CODE_FORBIDDEN, "该资料关联病例尚未加入实训，暂不可查看");
            }
        }

        resource.setViewCount((resource.getViewCount() != null ? resource.getViewCount() : 0) + 1);
        learningResourceMapper.updateById(resource);

        populateResourcesMetadata(List.of(resource), user);
        return resource;
    }

    @Transactional
    public LearningResource createResource(Map<String, Object> req, User user) {
        if (!isTeacherOrAdmin(user)) {
            throw new BusinessException(R.CODE_FORBIDDEN, "仅教师/管理员可上传学习资料");
        }

        String title = (String) req.get("title");
        if (title == null || title.trim().isEmpty()) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "资料标题不能为空");
        }

        Integer caseId = null;
        if (req.get("caseId") != null) {
            caseId = Integer.valueOf(req.get("caseId").toString());
        }

        LearningResource res = LearningResource.builder()
                .title(title.trim())
                .summary((String) req.getOrDefault("summary", ""))
                .content((String) req.getOrDefault("content", ""))
                .resourceType((String) req.getOrDefault("resourceType", "KNOWLEDGE"))
                .tags((String) req.getOrDefault("tags", ""))
                .coverUrl((String) req.getOrDefault("coverUrl", ""))
                .fileUrl((String) req.getOrDefault("fileUrl", ""))
                .fileType((String) req.getOrDefault("fileType", ""))
                .caseId(caseId)
                .status((String) req.getOrDefault("status", "PUBLISHED"))
                .publisherId(user.getId())
                .viewCount(0)
                .favoriteCount(0)
                .build();
        res.setCreatedAt(LocalDateTime.now());
        res.setUpdatedAt(LocalDateTime.now());
        learningResourceMapper.insert(res);

        populateResourcesMetadata(List.of(res), user);
        return res;
    }

    @Transactional
    public LearningResource updateResource(Integer id, Map<String, Object> req, User user) {
        LearningResource res = learningResourceMapper.selectById(id);
        if (res == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "资料不存在：" + id);
        }

        if (!isAdmin(user) && (user == null || !Objects.equals(res.getPublisherId(), user.getId()))) {
            throw new BusinessException(R.CODE_FORBIDDEN, "仅可编辑自己上传的资料");
        }
        if (!isTeacherOrAdmin(user)) {
            throw new BusinessException(R.CODE_FORBIDDEN, "无编辑权限");
        }

        if (req.containsKey("title") && req.get("title") != null) res.setTitle(req.get("title").toString());
        if (req.containsKey("summary")) res.setSummary((String) req.get("summary"));
        if (req.containsKey("content")) res.setContent((String) req.get("content"));
        if (req.containsKey("resourceType")) res.setResourceType((String) req.get("resourceType"));
        if (req.containsKey("tags")) res.setTags((String) req.get("tags"));
        if (req.containsKey("coverUrl")) res.setCoverUrl((String) req.get("coverUrl"));
        if (req.containsKey("fileUrl")) res.setFileUrl((String) req.get("fileUrl"));
        if (req.containsKey("fileType")) res.setFileType((String) req.get("fileType"));
        if (req.containsKey("status")) res.setStatus((String) req.get("status"));
        if (req.containsKey("caseId")) {
            res.setCaseId(req.get("caseId") != null ? Integer.valueOf(req.get("caseId").toString()) : null);
        }
        res.setUpdatedAt(LocalDateTime.now());
        learningResourceMapper.updateById(res);

        populateResourcesMetadata(List.of(res), user);
        return res;
    }

    @Transactional
    public void deleteResource(Integer id, User user) {
        LearningResource res = learningResourceMapper.selectById(id);
        if (res == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "资料不存在：" + id);
        }
        if (!isAdmin(user) && (user == null || !Objects.equals(res.getPublisherId(), user.getId()))) {
            throw new BusinessException(R.CODE_FORBIDDEN, "仅可删除自己上传的资料");
        }
        learningResourceMapper.deleteById(id);
    }

    public PageResult<LearningResource> listFavorites(
            long page, long pageSize, String keyword, String resourceType, String label, User user
    ) {
        LambdaQueryWrapper<ResourceFavorite> favQuery = new LambdaQueryWrapper<>();
        favQuery.eq(ResourceFavorite::getUserId, user.getId());
        if (label != null && !label.trim().isEmpty()) {
            favQuery.eq(ResourceFavorite::getLabel, label.trim());
        }
        favQuery.orderByDesc(ResourceFavorite::getId);

        List<ResourceFavorite> allFavs = resourceFavoriteMapper.selectList(favQuery);
        if (allFavs.isEmpty()) {
            return PageResult.of(0, page, pageSize, Collections.emptyList());
        }

        Map<Integer, String> favLabelMap = allFavs.stream()
                .collect(Collectors.toMap(ResourceFavorite::getResourceId, f -> f.getLabel() != null ? f.getLabel() : "", (a, b) -> a));

        List<Integer> resourceIds = allFavs.stream().map(ResourceFavorite::getResourceId).collect(Collectors.toList());

        LambdaQueryWrapper<LearningResource> resQuery = new LambdaQueryWrapper<>();
        resQuery.in(LearningResource::getId, resourceIds);
        if (keyword != null && !keyword.trim().isEmpty()) {
            String kw = keyword.trim();
            resQuery.and(q -> q.like(LearningResource::getTitle, kw)
                    .or().like(LearningResource::getSummary, kw)
                    .or().like(LearningResource::getTags, kw));
        }
        if (resourceType != null && !resourceType.trim().isEmpty()) {
            resQuery.eq(LearningResource::getResourceType, resourceType.trim());
        }

        List<LearningResource> matchingResources = learningResourceMapper.selectList(resQuery);

        Map<Integer, LearningResource> resourceMap = matchingResources.stream()
                .collect(Collectors.toMap(LearningResource::getId, r -> r));

        List<LearningResource> orderedList = new ArrayList<>();
        for (ResourceFavorite fav : allFavs) {
            LearningResource r = resourceMap.get(fav.getResourceId());
            if (r != null) {
                orderedList.add(r);
            }
        }

        long total = orderedList.size();
        int fromIndex = (int) Math.min((page - 1) * pageSize, total);
        int toIndex = (int) Math.min(fromIndex + pageSize, total);
        List<LearningResource> pagedList = fromIndex < toIndex ? orderedList.subList(fromIndex, toIndex) : Collections.emptyList();

        populateResourcesMetadata(pagedList, user);
        pagedList.forEach(r -> {
            r.setIsFavorited(true);
            r.setFavoriteLabel(favLabelMap.getOrDefault(r.getId(), ""));
        });

        return PageResult.of(total, page, pageSize, pagedList);
    }

    @Transactional
    public LearningResource addFavorite(Integer resourceId, String label, User user) {
        LearningResource res = learningResourceMapper.selectById(resourceId);
        if (res == null) {
            throw new BusinessException(R.CODE_NOT_FOUND, "资料不存在：" + resourceId);
        }
        if (!"PUBLISHED".equalsIgnoreCase(res.getStatus())) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "资料未发布，无法收藏");
        }

        ResourceFavorite existing = resourceFavoriteMapper.selectOne(new LambdaQueryWrapper<ResourceFavorite>()
                .eq(ResourceFavorite::getUserId, user.getId())
                .eq(ResourceFavorite::getResourceId, resourceId));

        if (existing != null) {
            existing.setLabel(label != null ? label : existing.getLabel());
            existing.setUpdatedAt(LocalDateTime.now());
            resourceFavoriteMapper.updateById(existing);
        } else {
            ResourceFavorite fav = ResourceFavorite.builder()
                    .userId(user.getId())
                    .resourceId(resourceId)
                    .label(label != null ? label : "")
                    .build();
            fav.setCreatedAt(LocalDateTime.now());
            fav.setUpdatedAt(LocalDateTime.now());
            resourceFavoriteMapper.insert(fav);

            res.setFavoriteCount((res.getFavoriteCount() != null ? res.getFavoriteCount() : 0) + 1);
            learningResourceMapper.updateById(res);
        }

        populateResourcesMetadata(List.of(res), user);
        res.setIsFavorited(true);
        res.setFavoriteLabel(label != null ? label : "");
        return res;
    }

    @Transactional
    public void removeFavorite(Integer resourceId, User user) {
        ResourceFavorite existing = resourceFavoriteMapper.selectOne(new LambdaQueryWrapper<ResourceFavorite>()
                .eq(ResourceFavorite::getUserId, user.getId())
                .eq(ResourceFavorite::getResourceId, resourceId));
        if (existing == null) return;

        resourceFavoriteMapper.deleteById(existing.getId());
        LearningResource res = learningResourceMapper.selectById(resourceId);
        if (res != null && res.getFavoriteCount() != null && res.getFavoriteCount() > 0) {
            res.setFavoriteCount(res.getFavoriteCount() - 1);
            learningResourceMapper.updateById(res);
        }
    }

    public PageResult<LearningNote> listNotes(
            long page, long pageSize, String keyword, Integer caseId, Integer resourceId, Integer targetUserId, User user
    ) {
        LambdaQueryWrapper<LearningNote> query = new LambdaQueryWrapper<>();
        if (isAdmin(user)) {
            if (targetUserId != null) {
                query.eq(LearningNote::getUserId, targetUserId);
            }
        } else {
            query.eq(LearningNote::getUserId, user.getId());
        }

        if (keyword != null && !keyword.trim().isEmpty()) {
            String kw = keyword.trim();
            query.and(q -> q.like(LearningNote::getTitle, kw)
                    .or().like(LearningNote::getContent, kw)
                    .or().like(LearningNote::getTags, kw));
        }

        if (caseId != null) {
            query.eq(LearningNote::getCaseId, caseId);
        }
        if (resourceId != null) {
            query.eq(LearningNote::getResourceId, resourceId);
        }

        query.orderByDesc(LearningNote::getUpdatedAt).orderByDesc(LearningNote::getId);

        Page<LearningNote> pageParam = new Page<>(Math.max(1, page), Math.max(1, Math.min(200, pageSize)));
        Page<LearningNote> result = learningNoteMapper.selectPage(pageParam, query);

        populateNotesMetadata(result.getRecords());
        return PageResult.of(result.getTotal(), page, pageSize, result.getRecords());
    }

    @Transactional
    public LearningNote createNote(Map<String, Object> req, User user) {
        String title = (String) req.getOrDefault("title", "");
        String content = (String) req.getOrDefault("content", "");
        if (title.trim().isEmpty() && content.trim().isEmpty()) {
            throw new BusinessException(R.CODE_BAD_REQUEST, "标题与正文不能同时为空");
        }

        Integer caseId = req.get("caseId") != null ? Integer.valueOf(req.get("caseId").toString()) : null;
        Integer resourceId = req.get("resourceId") != null ? Integer.valueOf(req.get("resourceId").toString()) : null;

        if (caseId != null) {
            TrainingCase tc = trainingCaseMapper.selectById(caseId);
            if (tc == null) throw new BusinessException(R.CODE_BAD_REQUEST, "病例不存在：" + caseId);
        }
        if (resourceId != null) {
            LearningResource lr = learningResourceMapper.selectById(resourceId);
            if (lr == null) throw new BusinessException(R.CODE_BAD_REQUEST, "资料不存在：" + resourceId);
        }

        Integer imageIndex = -1;
        if (req.get("imageIndex") != null) {
            imageIndex = Integer.valueOf(req.get("imageIndex").toString());
            if (imageIndex < 0) imageIndex = -1;
        }

        LearningNote note = LearningNote.builder()
                .userId(user.getId())
                .title(title)
                .content(content)
                .tags((String) req.getOrDefault("tags", ""))
                .caseId(caseId)
                .imageIndex(imageIndex)
                .imageUrl((String) req.getOrDefault("imageUrl", ""))
                .resourceId(resourceId)
                .build();
        note.setCreatedAt(LocalDateTime.now());
        note.setUpdatedAt(LocalDateTime.now());
        learningNoteMapper.insert(note);

        populateNotesMetadata(List.of(note));
        return note;
    }

    public LearningNote getNote(Integer id, User user) {
        LearningNote note = learningNoteMapper.selectById(id);
        if (note == null) throw new BusinessException(R.CODE_NOT_FOUND, "笔记不存在：" + id);
        if (!isAdmin(user) && !Objects.equals(note.getUserId(), user.getId())) {
            throw new BusinessException(R.CODE_FORBIDDEN, "无权查看该笔记");
        }
        populateNotesMetadata(List.of(note));
        return note;
    }

    @Transactional
    public LearningNote updateNote(Integer id, Map<String, Object> req, User user) {
        LearningNote note = learningNoteMapper.selectById(id);
        if (note == null) throw new BusinessException(R.CODE_NOT_FOUND, "笔记不存在：" + id);
        if (!isAdmin(user) && !Objects.equals(note.getUserId(), user.getId())) {
            throw new BusinessException(R.CODE_FORBIDDEN, "仅本人可编辑该笔记");
        }

        if (req.containsKey("title")) note.setTitle((String) req.get("title"));
        if (req.containsKey("content")) note.setContent((String) req.get("content"));
        if (req.containsKey("tags")) note.setTags((String) req.get("tags"));
        if (req.containsKey("caseId")) {
            note.setCaseId(req.get("caseId") != null ? Integer.valueOf(req.get("caseId").toString()) : null);
        }
        if (req.containsKey("imageIndex")) {
            note.setImageIndex(req.get("imageIndex") != null ? Integer.valueOf(req.get("imageIndex").toString()) : -1);
        }
        if (req.containsKey("imageUrl")) note.setImageUrl((String) req.get("imageUrl"));
        if (req.containsKey("resourceId")) {
            note.setResourceId(req.get("resourceId") != null ? Integer.valueOf(req.get("resourceId").toString()) : null);
        }
        note.setUpdatedAt(LocalDateTime.now());
        learningNoteMapper.updateById(note);

        populateNotesMetadata(List.of(note));
        return note;
    }

    @Transactional
    public void deleteNote(Integer id, User user) {
        LearningNote note = learningNoteMapper.selectById(id);
        if (note == null) throw new BusinessException(R.CODE_NOT_FOUND, "笔记不存在：" + id);
        if (!isAdmin(user) && !Objects.equals(note.getUserId(), user.getId())) {
            throw new BusinessException(R.CODE_FORBIDDEN, "仅本人或管理员可删除该笔记");
        }
        learningNoteMapper.deleteById(id);
    }

    private void populateResourcesMetadata(List<LearningResource> resources, User user) {
        if (resources == null || resources.isEmpty()) return;

        Set<Integer> pubIds = resources.stream()
                .map(LearningResource::getPublisherId)
                .filter(Objects::nonNull)
                .collect(Collectors.toSet());

        Map<Integer, String> userNames = new HashMap<>();
        if (!pubIds.isEmpty()) {
            List<User> users = userMapper.selectBatchIds(pubIds);
            for (User u : users) {
                String name = u.getRealName() != null && !u.getRealName().isEmpty() ? u.getRealName() : u.getUsername();
                userNames.put(u.getId(), name);
            }
        }

        Set<Integer> resIds = resources.stream().map(LearningResource::getId).collect(Collectors.toSet());
        Map<Integer, String> favLabelMap = new HashMap<>();
        if (user != null && !resIds.isEmpty()) {
            List<ResourceFavorite> favs = resourceFavoriteMapper.selectList(new LambdaQueryWrapper<ResourceFavorite>()
                    .eq(ResourceFavorite::getUserId, user.getId())
                    .in(ResourceFavorite::getResourceId, resIds));
            for (ResourceFavorite f : favs) {
                favLabelMap.put(f.getResourceId(), f.getLabel() != null ? f.getLabel() : "");
            }
        }

        for (LearningResource r : resources) {
            r.setPublisherName(userNames.getOrDefault(r.getPublisherId(), ""));
            r.setResourceTypeText(TYPE_TEXT.getOrDefault(r.getResourceType(), r.getResourceType()));
            r.setIsFavorited(favLabelMap.containsKey(r.getId()));
            r.setFavoriteLabel(favLabelMap.getOrDefault(r.getId(), ""));
        }
    }

    private void populateNotesMetadata(List<LearningNote> notes) {
        if (notes == null || notes.isEmpty()) return;

        Set<Integer> userIds = notes.stream().map(LearningNote::getUserId).filter(Objects::nonNull).collect(Collectors.toSet());
        Set<Integer> caseIds = notes.stream().map(LearningNote::getCaseId).filter(Objects::nonNull).collect(Collectors.toSet());
        Set<Integer> resIds = notes.stream().map(LearningNote::getResourceId).filter(Objects::nonNull).collect(Collectors.toSet());

        Map<Integer, String> userNames = new HashMap<>();
        if (!userIds.isEmpty()) {
            List<User> users = userMapper.selectBatchIds(userIds);
            for (User u : users) {
                userNames.put(u.getId(), u.getRealName() != null && !u.getRealName().isEmpty() ? u.getRealName() : u.getUsername());
            }
        }

        Map<Integer, TrainingCase> caseMap = new HashMap<>();
        if (!caseIds.isEmpty()) {
            List<TrainingCase> cases = trainingCaseMapper.selectBatchIds(caseIds);
            for (TrainingCase c : cases) {
                caseMap.put(c.getId(), c);
            }
        }

        Map<Integer, String> resTitles = new HashMap<>();
        if (!resIds.isEmpty()) {
            List<LearningResource> rList = learningResourceMapper.selectBatchIds(resIds);
            for (LearningResource lr : rList) {
                resTitles.put(lr.getId(), lr.getTitle());
            }
        }

        for (LearningNote n : notes) {
            n.setUserName(userNames.getOrDefault(n.getUserId(), ""));
            TrainingCase tc = caseMap.get(n.getCaseId());
            if (tc != null) {
                n.setCaseNo(tc.getCaseNo() != null ? tc.getCaseNo() : "");
                n.setCaseTitle(tc.getTitle() != null ? tc.getTitle() : "");
            } else {
                n.setCaseNo("");
                n.setCaseTitle("");
            }
            n.setResourceTitle(resTitles.getOrDefault(n.getResourceId(), ""));
        }
    }
}
