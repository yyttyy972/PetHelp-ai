import {test,expect} from '@playwright/test';
test('双方确认、完成记录及宠主核验的角色约束',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'预约与执行',exact:true}).click();
 await page.getByRole('button',{name:'邀请并核对预约'}).click();
 await expect(page.getByRole('button',{name:'确认约定',exact:true})).toBeDisabled();
 await page.getByRole('checkbox').check();await page.getByRole('button',{name:'确认约定',exact:true}).click();
 await page.getByLabel('当前演示角色').selectOption('helper');await page.getByRole('checkbox').check();await page.getByRole('button',{name:'确认约定',exact:true}).click();
 await page.getByRole('button',{name:'模拟进入服务时间并开始'}).click();
 await expect(page.getByRole('button',{name:'提交宠主核验',exact:true})).toBeDisabled();
 await page.getByRole('button',{name:'保存此项完成记录'}).first().click();await expect(page.getByRole('alert')).toContainText('请填写');
 await page.getByLabel('本次完成情况').fill('按约定完成喂食');await page.getByRole('button',{name:'保存此项完成记录'}).first().click();
 await page.getByLabel('本次完成情况').fill('水碗已清洗并换水');await page.getByRole('button',{name:'保存此项完成记录'}).click();
 await page.getByRole('button',{name:'提交宠主核验',exact:true}).click();await page.getByRole('checkbox').check();await expect(page.getByRole('button',{name:'确认完成',exact:true})).toBeDisabled();
 await page.getByLabel('当前演示角色').selectOption('owner');await page.getByRole('button',{name:'确认完成',exact:true}).click();await expect(page.getByRole('heading',{name:'服务已完成'})).toBeVisible();
});
