package com.huiyan.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.huiyan.entity.User;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface UserMapper extends BaseMapper<User> {
}
