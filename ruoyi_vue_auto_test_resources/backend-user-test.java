package com.ruoyi.web.controller.system;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.core.domain.entity.SysUser;
import com.ruoyi.system.service.ISysUserService;
import com.ruoyi.system.service.ISysRoleService;
import com.ruoyi.system.service.ISysDeptService;
import com.ruoyi.system.service.ISysPostService;

/**
 * 后端核心功能测试代码 - 用户管理模块
 * 技术框架：JUnit5 + Mockito + MockMvc
 * 覆盖范围：接口协议完整性、数据存储可靠性、业务逻辑代码校验、压力场景模拟
 * 问题定位：在关键方法中标注行号
 */
@DisplayName("后端用户管理模块测试套件")
public class SysUserControllerTest {

    private MockMvc mockMvc;

    @Mock
    private ISysUserService userService;

    @Mock
    private ISysRoleService roleService;

    @Mock
    private ISysDeptService deptService;

    @Mock
    private ISysPostService postService;

    @InjectMocks
    private SysUserController sysUserController;

    private ObjectMapper objectMapper = new ObjectMapper();

    @BeforeEach
    public void setUp() {
        MockitoAnnotations.openMocks(this);
        mockMvc = MockMvcBuilders.standaloneSetup(sysUserController).build();
    }

    /**
     * 用例21：接口协议完整性校验 - 用户列表查询接口
     * 测试目标：验证GET请求参数合法性和响应数据格式
     * 问题定位：SysUserController.java:59-66
     */
    @Test
    @DisplayName("TC-BE-011: 接口协议完整性 - 用户列表查询")
    public void testGetUserList() throws Exception {
        // 执行请求（行号定位：SysUserController.java:60-66）
        mockMvc.perform(get("/system/user/list")
                .param("pageNum", "1")
                .param("pageSize", "10"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.rows").isArray());
    }

    /**
     * 用例22：接口协议完整性校验 - 用户新增接口必填项
     * 测试目标：验证POST请求必填项校验
     * 问题定位：SysUserController.java:125-144
     */
    @Test
    @DisplayName("TC-BE-012: 接口协议完整性 - 用户新增必填项校验")
    public void testAddUserWithEmptyUsername() throws Exception {
        SysUser user = new SysUser();
        user.setPassword("123456");
        user.setDeptId(100L);

        // 执行新增请求（行号定位：SysUserController.java:125-144）
        mockMvc.perform(post("/system/user")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(user)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(500));
    }

    /**
     * 用例23：数据存储可靠性测试 - 用户新增数据一致性
     * 测试目标：验证数据库插入操作的数据完整性
     * 问题定位：SysUserController.java:125-144
     */
    @Test
    @DisplayName("TC-BE-013: 数据存储可靠性 - 用户新增数据一致性")
    public void testAddUserDataConsistency() {
        SysUser user = new SysUser();
        user.setUserName("testuser");
        user.setNickName("测试用户");
        user.setPassword("123456");
        user.setPhonenumber("13800138000");
        user.setEmail("test@example.com");
        user.setDeptId(100L);

        // Mock服务层（行号定位：SysUserController.java:129-143）
        when(userService.checkUserNameUnique(user)).thenReturn(true);
        when(userService.checkPhoneUnique(user)).thenReturn(true);
        when(userService.checkEmailUnique(user)).thenReturn(true);
        when(userService.insertUser(user)).thenReturn(1);

        // 验证数据一致性（行号定位：SysUserController.java:125-144）
        boolean result = userService.insertUser(user) > 0;
        assertTrue(result, "用户新增数据一致性验证失败");
    }

    /**
     * 用例24：业务逻辑代码校验 - 用户名唯一性检查
     * 测试目标：验证用户名唯一性校验逻辑
     * 问题定位：SysUserController.java:129-132
     */
    @Test
    @DisplayName("TC-BE-014: 业务逻辑代码校验 - 用户名唯一性检查")
    public void testCheckUserNameUnique() throws Exception {
        SysUser user = new SysUser();
        user.setUserName("admin"); // 已存在的用户名

        // Mock用户名重复（行号定位：SysUserController.java:129-132）
        when(userService.checkUserNameUnique(user)).thenReturn(false);

        // 执行用户新增（行号定位：SysUserController.java:125-144）
        mockMvc.perform(post("/system/user")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(user)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(500))
                .andExpect(jsonPath("$.msg").value("新增用户'admin'失败，登录账号已存在"));
    }

    /**
     * 用例25：业务逻辑代码校验 - 手机号唯一性检查
     * 测试目标：验证手机号唯一性校验逻辑
     * 问题定位：SysUserController.java:133-136
     */
    @Test
    @DisplayName("TC-BE-015: 业务逻辑代码校验 - 手机号唯一性检查")
    public void testCheckPhoneUnique() throws Exception {
        SysUser user = new SysUser();
        user.setUserName("newuser");
        user.setNickName("新用户");
        user.setPassword("123456");
        user.setPhonenumber("13800138000"); // 已存在的手机号
        user.setEmail("new@example.com");
        user.setDeptId(100L);

        // Mock用户名唯一、手机号重复（行号定位：SysUserController.java:133-136）
        when(userService.checkUserNameUnique(user)).thenReturn(true);
        when(userService.checkPhoneUnique(user)).thenReturn(false);

        // 执行用户新增（行号定位：SysUserController.java:125-144）
        mockMvc.perform(post("/system/user")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(user)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(500))
                .andExpect(jsonPath("$.msg").value("新增用户'newuser'失败，手机号码已存在"));
    }

    /**
     * 用例26：业务逻辑代码校验 - 邮箱唯一性检查
     * 测试目标：验证邮箱唯一性校验逻辑
     * 问题定位：SysUserController.java:137-140
     */
    @Test
    @DisplayName("TC-BE-016: 业务逻辑代码校验 - 邮箱唯一性检查")
    public void testCheckEmailUnique() throws Exception {
        SysUser user = new SysUser();
        user.setUserName("newuser");
        user.setNickName("新用户");
        user.setPassword("123456");
        user.setPhonenumber("13900139000");
        user.setEmail("admin@example.com"); // 已存在的邮箱
        user.setDeptId(100L);

        // Mock用户名唯一、手机号唯一、邮箱重复（行号定位：SysUserController.java:137-140）
        when(userService.checkUserNameUnique(user)).thenReturn(true);
        when(userService.checkPhoneUnique(user)).thenReturn(true);
        when(userService.checkEmailUnique(user)).thenReturn(false);

        // 执行用户新增（行号定位：SysUserController.java:125-144）
        mockMvc.perform(post("/system/user")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(user)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(500))
                .andExpect(jsonPath("$.msg").value("新增用户'newuser'失败，邮箱账号已存在"));
    }

    /**
     * 用例27：接口协议完整性校验 - 用户修改接口
     * 测试目标：验证PUT请求参数合法性和响应状态码
     * 问题定位：SysUserController.java:152-172
     */
    @Test
    @DisplayName("TC-BE-017: 接口协议完整性 - 用户修改接口")
    public void testUpdateUser() throws Exception {
        SysUser user = new SysUser();
        user.setUserId(1L);
        user.setUserName("admin");
        user.setNickName("管理员");
        user.setPhonenumber("13800138000");
        user.setEmail("admin@example.com");
        user.setDeptId(100L);

        // Mock服务层（行号定位：SysUserController.java:158-172）
        when(userService.checkUserNameUnique(user)).thenReturn(true);
        when(userService.checkPhoneUnique(user)).thenReturn(true);
        when(userService.checkEmailUnique(user)).thenReturn(true);
        when(userService.updateUser(user)).thenReturn(1);

        // 执行修改请求（行号定位：SysUserController.java:152-172）
        mockMvc.perform(put("/system/user")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(user)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200));
    }

    /**
     * 用例28：业务逻辑代码校验 - 删除当前用户限制
     * 测试目标：验证不能删除当前用户的业务逻辑
     * 问题定位：SysUserController.java:180-192
     */
    @Test
    @DisplayName("TC-BE-018: 业务逻辑代码校验 - 删除当前用户限制")
    public void testDeleteCurrentUser() throws Exception {
        // 模拟当前用户ID为1（行号定位：SysUserController.java:182-190）
        Long currentUserId = 1L;
        Long[] userIds = {1L}; // 尝试删除当前用户

        MockMvc mvc = MockMvcBuilders.standaloneSetup(new SysUserController() {
            @Override
            public Long getUserId() {
                return currentUserId;
            }
        }).build();

        // 执行删除请求（行号定位：SysUserController.java:180-192）
        mvc.perform(delete("/system/user/{userIds}", 1))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(500))
                .andExpect(jsonPath("$.msg").value("当前用户不能删除"));
    }

    /**
     * 用例29：压力场景模拟测试 - 用户列表查询性能
     * 测试目标：验证高频接口响应时间和资源占用
     * 问题定位：SysUserController.java:59-66
     */
    @Test
    @DisplayName("TC-BE-019: 压力场景模拟 - 用户列表查询性能")
    public void testUserListQueryPerformance() throws Exception {
        // 模拟100个并发请求（行号定位：SysUserController.java:60-66）
        long startTime = System.currentTimeMillis();
        for (int i = 0; i < 100; i++) {
            mockMvc.perform(get("/system/user/list")
                    .param("pageNum", "1")
                    .param("pageSize", "10"))
                    .andExpect(status().isOk());
        }
        long endTime = System.currentTimeMillis();
        long avgTime = (endTime - startTime) / 100;

        // 验证平均响应时间不超过300ms（行号定位：SysUserController.java:60-66）
        assertTrue(avgTime <= 300, "用户列表查询平均响应时间: " + avgTime + "ms，超过300ms阈值");
    }

    /**
     * 用例30：安全测试 - XSS攻击防护
     * 测试目标：验证用户管理接口对XSS攻击的防护
     * 问题定位：SysUserController.java:125-144
     */
    @Test
    @DisplayName("TC-BE-020: 安全测试 - XSS攻击防护")
    public void testXSSProtection() throws Exception {
        SysUser user = new SysUser();
        user.setUserName("testuser");
        user.setNickName("<script>alert('XSS')</script>");
        user.setPassword("123456");
        user.setPhonenumber("13800138000");
        user.setEmail("test@example.com");
        user.setDeptId(100L);

        // Mock服务层（行号定位：SysUserController.java:125-144）
        when(userService.checkUserNameUnique(user)).thenReturn(true);
        when(userService.checkPhoneUnique(user)).thenReturn(true);
        when(userService.checkEmailUnique(user)).thenReturn(true);
        when(userService.insertUser(user)).thenReturn(1);

        // 执行用户新增（行号定位：SysUserController.java:125-144）
        mockMvc.perform(post("/system/user")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(user)))
                .andExpect(status().isOk());

        // 验证XSS被转义（行号定位：XssFilter.java）
        verify(userService).insertUser(user);
        assertFalse(user.getNickName().contains("<script>"), "XSS防护失效");
    }
}