import logo from './assets/tizhuang-logo.svg';

// Website letter positions, rendered in the current Obsidian text colour.
// Source: https://tizhuang.qcscience.cc/brand/tizhuang-logo-subtle.svg?v=13
export function renderBrand(parent){
  const brand=document.createElement('div');brand.className='tz-brand';
  const mark=document.createElement('span');mark.className='tz-brand-mark';mark.setAttribute('aria-hidden','true');
  // Static bundled SVG only; inline rendering lets currentColor follow the theme.
  mark.innerHTML=logo;
  const title=document.createElement('h2');title.textContent='本地题库';
  brand.append(mark,title);parent.append(brand);return brand;
}
