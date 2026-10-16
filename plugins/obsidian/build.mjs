import {build} from 'esbuild';
import {mkdir, copyFile} from 'node:fs/promises';
await mkdir('dist/tizhuang-question-bank', {recursive:true});
await build({entryPoints:['src/main.js'],bundle:true,platform:'browser',format:'cjs',loader:{'.svg':'text'},external:['obsidian','child_process','electron'],target:'es2020',outfile:'dist/tizhuang-question-bank/main.js',logLevel:'info'});
for(const name of ['manifest.json','styles.css','README.md']) await copyFile(name,`dist/tizhuang-question-bank/${name}`);
await mkdir('dist/tizhuang-question-bank/helper',{recursive:true});
for(const name of ['auto_classify.py','paper_links.py','local_bank.py','ui_layout.py','teacher_library.py','pdf_import.py','paper_builder.py','docx_export.py','doctor.py','paper-print.css','requirements.txt'])await copyFile(`../../skills/tizhuang-local-bank/scripts/${name}`,`dist/tizhuang-question-bank/helper/${name}`);
