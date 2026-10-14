// Verify the standalone HTML with all external requests blocked.
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const require=createRequire(import.meta.url),runtime=process.env.TZ_PREVIEW_NODE_MODULES;
const {chromium}=require(runtime?path.join(runtime,'playwright'):'playwright');
const html=await readFile(path.join(root,'templates/local-bank-starter/先看这里.html'),'utf8');
const out=process.env.TZ_GUIDE_CHECK_OUTPUT;assert(out,'Set TZ_GUIDE_CHECK_OUTPUT outside the release archive');await mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true,...(process.env.TZ_PREVIEW_BROWSER?{executablePath:process.env.TZ_PREVIEW_BROWSER}:{})});
const reports=[];
try{for(const width of [1280,390]){
 const page=await browser.newPage({viewport:{width,height:1000},deviceScaleFactor:1});const errors=[],requests=[];
 page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>{requests.push(r.request().url());return r.abort();});
 await page.setContent(html);await page.evaluate(()=>document.fonts.ready);
 const state=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,images:[...document.querySelectorAll('main img')].map(i=>({src:i.src.startsWith('data:image/png;base64,'),loaded:i.complete&&i.naturalWidth>0})),badAnchors:[...document.querySelectorAll('a[href^="#"]')].filter(a=>!document.getElementById(a.getAttribute('href').slice(1))).map(a=>a.getAttribute('href')),prompts:document.querySelectorAll('pre').length}));
 assert.equal(state.width,state.scroll);assert.equal(state.images.length,8);assert(state.images.every(i=>i.src&&i.loaded));assert.equal(state.badAnchors.length,0);assert.equal(state.prompts,6);
 await page.locator('pre button').first().click();assert.equal(await page.locator('pre button').first().textContent(),'已复制');
 await page.locator('main img').first().click();assert(await page.locator('dialog').evaluate(d=>d.open));await page.getByRole('button',{name:'关闭 ×'}).click();
 await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(out,'guide-'+width+'.png')});
 assert.equal(errors.length,0);assert.equal(requests.length,0);reports.push({width,images:state.images.length,prompts:state.prompts,overflow:false,copy:true,zoom:true,networkRequests:requests.length,errors});await page.close();
}}finally{await browser.close();}
await writeFile(path.join(out,'verification.json'),JSON.stringify(reports,null,2)+'\n');console.log(JSON.stringify(reports));
