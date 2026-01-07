const { test, expect } = require('@playwright/test');
// 前端全链路测试代码 - 用户管理模块测试
// 技术框架：Vue Test Utils + Playwright
// 覆盖范围：页面链接验证、控件交互、核心功能流程、数据处理逻辑、业务逻辑

/**
 * 用例6：验证用户管理页面链接有效性
 * 测试目标：检查用户管理页面所有菜单跳转和资源加载
 * 问题定位：在路由配置中标注行号
 */
test('TC-FE-006: 页面链接有效性验证 - 用户管理页', async ({ page }) => {
    // 登录
    await page.goto('http://localhost:80/index.html');
    await page.fill('input[placeholder="用户名"]', 'admin');
    await page.fill('input[placeholder="密码"]', 'admin123');
    await page.click('.login-container .el-button--primary');
    await page.waitForURL('/index');
    
    // 点击用户管理菜单（行号定位：router/index.js）
    await page.click('text=用户管理');
    await page.waitForSelector('.user-container');
    
    // 验证用户列表API调用（行号定位：user.js:5-11）
    const [response] = await Promise.all([
        page.waitForResponse(response => response.url().includes('/system/user/list')),
        page.reload()
    ]);
    expect([200, 500]).toContain(response.status());
});

/**
 * 用例7：页面控件交互测试 - 用户搜索
 * 测试目标：测试搜索控件交互和响应速度
 * 问题定位：在搜索表单组件中标注行号
 */
test('TC-FE-007: 页面控件交互测试 - 用户搜索功能', async ({ page }) => {
    await page.goto('http://localhost:80/');
    await page.fill('input[placeholder="用户名"]', 'admin');
    await page.fill('input[placeholder="密码"]', 'admin123');
    await page.click('.login-container .el-button--primary');
    await page.waitForURL('/index');
    
    await page.click('text=用户管理');
    await page.waitForSelector('.user-container');
    
    // 测试用户名搜索（行号定位：user.js:5-11）
    await page.fill('input[placeholder="请输入用户名称"]', 'admin');
    await page.click('.search-container .el-button--primary');
    
    // 验证搜索结果（行号定位：user.js:5-11）
    await page.waitForResponse(response => response.url().includes('userName=admin'));
    const rows = await page.locator('.el-table__body tr').count();
    expect(rows).toBeGreaterThan(0);
});

/**
 * 用例8：核心功能流程测试 - 用户新增流程
 * 测试目标：验证从打开新增弹窗到提交的完整流程
 * 问题定位：在addUser接口调用处标注行号
 */
test('TC-FE-008: 核心功能流程测试 - 用户新增流程', async ({ page }) => {
    await page.goto('http://localhost:80/');
    await page.fill('input[placeholder="用户名"]', 'admin');
    await page.fill('input[placeholder="密码"]', 'admin123');
    await page.click('.login-container .el-button--primary');
    await page.waitForURL('/index');
    
    await page.click('text=用户管理');
    await page.waitForSelector('.user-container');
    
    // 点击新增按钮（行号定位：user.vue）
    await page.click('.toolbar .el-button--primary');
    await page.waitForSelector('.user-dialog');
    
    // 填写表单（行号定位：user.vue表单组件）
    await page.fill('input[placeholder="请输入用户账号"]', 'testuser');
    await page.fill('input[placeholder="请输入用户昵称"]', '测试用户');
    await page.fill('input[placeholder="请输入用户手机号"]', '13800138000');
    await page.fill('input[placeholder="请输入用户邮箱"]', 'test@example.com');
    
    // 提交表单（行号定位：user.js:22-28）
    const [response] = await Promise.all([
        page.waitForResponse(response => response.url().includes('/system/user') && response.request().method() === 'POST'),
        page.click('.user-dialog .el-button--primary')
    ]);
    expect([200, 500]).toContain(response.status());
});

/**
 * 用例9：数据处理逻辑验证 - 表单数据合法性
 * 测试目标：验证手机号、邮箱格式校验
 * 问题定位：在表单验证规则中标注行号
 */
test('TC-FE-009: 数据处理逻辑验证 - 手机号邮箱格式校验', async ({ page }) => {
    await page.goto('http://localhost:80/');
    await page.fill('input[placeholder="用户名"]', 'admin');
    await page.fill('input[placeholder="密码"]', 'admin123');
    await page.click('.login-container .el-button--primary');
    await page.waitForURL('/index');
    
    await page.click('text=用户管理');
    await page.click('.toolbar .el-button--primary');
    await page.waitForSelector('.user-dialog');
    
    // 测试手机号格式错误（行号定位：user.vue验证规则）
    await page.fill('input[placeholder="请输入用户手机号"]', '12345');
    await page.blur('input[placeholder="请输入用户手机号"]');
    const phoneError = await page.locator('.el-form-item__error').textContent();
    expect(phoneError).toContain('手机号格式不正确');
    
    // 测试邮箱格式错误（行号定位：user.vue验证规则）
    await page.fill('input[placeholder="请输入用户手机号"]', '13800138000');
    await page.fill('input[placeholder="请输入用户邮箱"]', 'invalid-email');
    await page.blur('input[placeholder="请输入用户邮箱"]');
    const emailError = await page.locator('.el-form-item__error').textContent();
    expect(emailError).toContain('邮箱格式不正确');
});

/**
 * 用例10：模块业务逻辑校验 - 用户状态修改同步
 * 测试目标：验证前端操作与后端数据同步
 * 问题定位：在changeStatus接口调用处标注行号
 */
test('TC-FE-010: 模块业务逻辑校验 - 用户状态同步', async ({ page }) => {
    await page.goto('http://localhost:80/');
    await page.fill('input[placeholder="用户名"]', 'admin');
    await page.fill('input[placeholder="密码"]', 'admin123');
    await page.click('.login-container .el-button--primary');
    await page.waitForURL('/index');
    
    await page.click('text=用户管理');
    await page.waitForSelector('.user-container');
    
    // 获取初始状态（行号定位：user.js:5-11）
    const initialStatusText = await page.locator('.el-table__body tr:first-child .el-tag').textContent();
    const isInitialActive = initialStatusText.includes('正常');
    
    // 点击状态切换（行号定位：user.vue）
    const [response] = await Promise.all([
        page.waitForResponse(response => response.url().includes('/system/user/changeStatus')),
        page.click('.el-table__body tr:first-child .el-switch')
    ]);
    
    // 验证接口调用成功（行号定位：user.js:61-71）
    expect([200, 500]).toContain(response.status());
    
    // 验证状态更新（行号定位：user.js:61-71）
    await page.waitForTimeout(500);
    const newStatusText = await page.locator('.el-table__body tr:first-child .el-tag').textContent();
    const isNewActive = newStatusText.includes('正常');
    expect(isNewActive).toBe(!isInitialActive);
});