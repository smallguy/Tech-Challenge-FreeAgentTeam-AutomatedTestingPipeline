const { test, expect } = require('@playwright/test');
// 前端全链路测试代码 - 登录模块测试
// 技术框架：Vue Test Utils + Playwright
// 覆盖范围：页面链接验证、控件交互、核心功能流程

/**
 * 用例1：验证登录页面所有链接有效性
 * 测试目标：检查登录页面所有内部链接和外部资源是否存在
 * 问题定位：若链接失效，在页面元素选择器中标注行号
 */
test('TC-FE-001: 页面链接有效性验证 - 登录页', async ({ page }) => {
    await page.goto('http://localhost:80/index.html');
    
    // 验证验证码图片链接（行号定位：login.js:51-60）
    const captchaResponse = await page.goto('/captchaImage');
    expect(captchaResponse.status()).toBe(200);
    
    // 验证登录接口链接（行号定位：login.js:12）
    const loginRequest = await page.request.post('http://localhost:80/login', {
        data: { username: 'admin', password: 'admin123', code: '1234', uuid: 'test' }
    });
    expect([200, 401, 500]).toContain(loginRequest.status());
});

/**
 * 用例2：验证登录控件交互 - 缺少必填项
 * 测试目标：测试必填项校验，验证错误提示
 * 问题定位：在validateLoginForm函数中标注行号
 */
test('TC-FE-002: 页面控件交互测试 - 登录表单验证', async ({ page }) => {
    await page.goto('http://localhost:80/index.html');
    
    // 测试空用户名提示（行号定位：SysLoginController.java:60-63）
    await page.click('.login-container .el-button--primary');
    const userNameError = await page.locator('.el-message').textContent();
    expect(userNameError).toContain('用户名不能为空');
    
    // 测试空密码提示（行号定位：SysLoginController.java:65-68）
    await page.fill('input[placeholder="用户名"]', 'admin');
    await page.click('.login-container .el-button--primary');
    const passwordError = await page.locator('.el-message').textContent();
    expect(passwordError).toContain('密码不能为空');
});

/**
 * 用例3：核心功能流程测试 - 完整登录流程
 * 测试目标：验证从登录到获取用户信息的完整流程
 * 问题定位：在login和getInfo接口调用处标注行号
 */
test('TC-FE-003: 核心功能流程测试 - 登录成功流程', async ({ page }) => {
    // 步骤1：获取验证码（行号定位：login.js:51-60）
    await page.goto('http://localhost:80/index.html');
    const captchaImg = await page.locator('.captcha-img').getAttribute('src');
    expect(captchaImg).toContain('/captchaImage');
    
    // 步骤2：输入用户名密码（行号定位：login.js:4-19）
    await page.fill('input[placeholder="用户名"]', 'admin');
    await page.fill('input[placeholder="密码"]', 'admin123');
    
    // 步骤3：提交登录（行号定位：SysLoginController.java:56-81）
    await page.click('.login-container .el-button--primary');
    await page.waitForURL('/index');
    
    // 步骤4：验证获取用户信息（行号定位：SysLoginController.java:88-117）
    const userInfo = await page.evaluate(() => {
        return localStorage.getItem('userinfo');
    });
    expect(userInfo).not.toBeNull();
});

/**
 * 用例4：数据处理逻辑验证 - 密码加密
 * 测试目标：验证前端密码加密逻辑
 * 问题定位：在加密函数中标注行号
 */
test('TC-FE-004: 数据处理逻辑验证 - 密码格式校验', async ({ page }) => {
    await page.goto('http://localhost:80/index.html');
    
    // 测试密码长度验证（行号定位：前端校验函数）
    await page.fill('input[placeholder="用户名"]', 'admin');
    await page.fill('input[placeholder="密码"]', '123');
    await page.click('.login-container .el-button--primary');
    const error = await page.locator('.el-message').textContent();
    expect(error).toContain('密码长度不能少于5位');
    
    // 测试密码复杂度验证（行号定位：前端校验函数）
    await page.fill('input[placeholder="密码"]', '111111');
    const complexError = await page.locator('.el-message').textContent();
    expect(complexError).toContain('密码必须包含字母和数字');
});

/**
 * 用例5：模块业务逻辑校验 - Token管理
 * 测试目标：验证Token的存储和使用
 * 问题定位：在Token存储逻辑中标注行号
 */
test('TC-FE-005: 模块业务逻辑校验 - Token双向同步', async ({ page }) => {
    await page.goto('http://localhost:80/index.html');
    
    // 登录获取Token（行号定位：login.js:11-19）
    await page.fill('input[placeholder="用户名"]', 'admin');
    await page.fill('input[placeholder="密码"]', 'admin123');
    await page.click('.login-container .el-button--primary');
    await page.waitForTimeout(1000);
    
    // 验证Token存储在localStorage（行号定位：request.js）
    const token = await page.evaluate(() => localStorage.getItem('Admin-Token'));
    expect(token).not.toBeNull();
    
    // 验证Token在请求头中传递（行号定位：request.js）
    const [request] = await Promise.all([
        page.waitForResponse(response => response.url().includes('/getInfo')),
        page.goto('/index')
    ]);
    expect(request.headers()['authorization']).toContain('Bearer');
});