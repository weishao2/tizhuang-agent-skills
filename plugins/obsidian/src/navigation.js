import {Notice} from 'obsidian';
export const NAVIGATION=[['home','首页'],['website','网站取题'],['questions','我的题目'],['basket','组卷篮'],['pdf','PDF 导入']];
export function renderNavigation(parent,view,active){
 const nav=document.createElement('nav');nav.className='tz-lib-tabs';nav.setAttribute('aria-label','本地题库导航');parent.append(nav);
 for(const[id,label]of NAVIGATION){const button=document.createElement('button');button.type='button';button.className='tz-quiet';button.dataset.tab=id;button.textContent=id==='basket'&&view.plugin.basket?.data.items.length?`${label}（${view.plugin.basket.data.items.length}）`:label;button.classList.toggle('is-active',id===active);if(id===active)button.setAttribute('aria-current','page');button.onclick=()=>{if(view.plugin.localTaskActive||view.plugin.store?.busy||view.plugin.basket?.busy){new Notice('正在保存题库，请稍候再切换。');return;}return id===active?undefined:id==='website'?view.plugin.open(view.leaf):view.plugin.openLibrary(id,view.leaf);};nav.append(button);}
 return nav;
}
