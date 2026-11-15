import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {PresentationFile,FileBlob} from '@oai/artifact-tool';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const build=path.join(root,'qa/final-v3-r3');await fs.mkdir(build,{recursive:true});
const source=path.join(root,'outputs/customer_support_project_presentation.pptx');
const skill='C:/Users/Administrator/.codex/plugins/cache/openai-primary-runtime/presentations/26.1112.11011/skills/presentations';
process.env.RUNTIME_NODE_MODULES='C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const content=JSON.parse(await fs.readFile(path.join(root,'qa/presentation_content.json'),'utf8'));
const p=await PresentationFile.importPptx(await FileBlob.load(source));
if(p.slides.items.length!==10)throw Error('Expected existing ten slides');
function at(i,x,y){const sh=p.slides.getItem(i-1).shapes.items.find(e=>Math.abs(e.position.left-x)<1&&Math.abs(e.position.top-y)<1);if(!sh)throw Error(`Missing ${i}:${x},${y}`);return sh;}
function put(i,x,y,t,size){const sh=at(i,x,y);sh.text=t;if(size){const teal=(i===1&&y===500)||(i===5&&y===224)||(i===7&&y===490)||(i===8&&y===510)||(i===9&&y===219);sh.text.style={fontSize:size,typeface:'Arial',color:teal?'#096C6D':y===94?'#132D46':'#172B3A',bold:teal||y===94,insets:0,wrap:'square',autoFit:'none'};}}
function table(i,values){const t=p.slides.getItem(i-1).tables.items[0];for(let r=0;r<values.length;r++)for(let c=0;c<values[r].length;c++)t.getCell(r,c).value=values[r][c];}
put(1,64,303,'Final v3 refund rules.\nHuman annotations and a calibrated LLM judge.');
put(1,64,500,'V3 Exact Match 100%  •  Judge v2 100%',40);
put(1,64,588,'Known 100-ticket dataset • Presentation + 90-second demo',24);
table(3,[['Stage','Tool / action','Evidence'],['Predict','gpt-4o-mini; temperature 0','100 outputs per version'],['Score','Exact Match; same final labels','Baseline / focused / v3'],['Review','Excel notes + approval','Separate t033 human review'],['Record','LangSmith traces + feedback','Old and new judge scores']]);
put(3,64,605,'LLM judge: gpt-5.4-mini-2026-03-17; grading uses separate API calls.',24);
put(5,64,94,'V3 clarifies the refund exceptions',44);
put(5,64,224,'A missing refund payment is a refund issue.\nA damaged product stays product_issue.',39);
put(5,64,404,'Returned item + refund money missing → refund_request',29);
put(5,64,478,'Unwanted-order cancellation + refund → refund_request\nActual non-delivery → order_status',29);
put(5,64,591,'Six focused-model errors corrected; no new classification failures.',25);
put(6,64,295,'L: review notes; M: approval\nFinal t046 policy: product_issue\nt033: refund_request, separate review',27);
put(6,64,478,'8/8 baseline + 7/7 focused\n15 completed run reviews\n14 tickets; 75 feedback records\nScreenshot: preserved earlier review',25);
table(7,[['Scoring basis','Baseline','Focused','V3'],['Same final policy','92 / 100','94 / 100','100 / 100'],['Earlier reviewed policy','93 / 100','93 / 100','—']]);
put(7,64,490,'Six model fixes: t024–t029 • Zero regressions',31);
put(7,64,562,'t046 now uses product_issue consistently for damaged goods.\nOld 93% → 100% includes one label-policy point + six model fixes.',26);
put(8,64,37,'FINAL ADD-ON / LLM AS A JUDGE');
at(8,64,37).text.style={fontSize:18,typeface:'Arial',color:'#096C6D',bold:true,insets:0,wrap:'square',autoFit:'none'};
put(8,64,94,'Judge calibration: 99% → 100%',44);
put(8,64,207,'All 100 saved v3 outputs assessed again\ngpt-5.4-mini-2026-03-17 • general billing/refund clarification',27);
table(8,[['Measure','Before','Final'],['LLM judge passes','99 / 100','100 / 100'],['Classifier Exact Match','100 / 100','100 / 100']]);
put(8,64,510,'Only t033 changed score; 12 ambiguity flags remain, all passing.',25);
put(8,64,563,'Overcharge reimbursement → refund_request.\nOld automated 0, separate human 1, new automated 1 are retained.',26);
put(9,64,94,'Measured improvement on the known dataset',44);
put(9,64,219,'Classifier 100%  •  Calibrated judge 100%',37);
put(9,64,324,'What the evidence supports',30);
put(9,64,381,'Six classification fixes and one judge-score correction.\nNo regressions; previous predictions and scores preserved.',29);
put(9,64,520,'Next: independent tickets and repeated judge assessments.\nKnown-example calibration does not establish universal accuracy.',27);
const cues=[['00:00','Report: 92% / 94% / 100% under one label policy'],['00:15','V3 workbook: six green fixes; t046 policy in purple'],['00:35','Judge v2 review: t033 and preserved earlier score'],['00:50','LangSmith: Exact Match, both judges, human feedback'],['01:12','Notebook, GitHub, ambiguity flags and limitations']];
cues.forEach(([t,c],i)=>{put(10,64,223+i*77,t);put(10,220,223+i*77,c,28);});
const sources='\n\nSources: v3/results/comparison.json; v3/results/ticket_comparison.csv; v3/llm_judge/summary.json; v3/llm_judge_v2/before_after.json; v3/human_reviews/t033.json; v3/results/langsmith_v3_evidence.json. The historical workbook and original scores remain unchanged.';
for(let i=0;i<9;i++){
 const slide=p.slides.getItem(i);const previous=String(slide.speakerNotes.text??'');
 slide.speakerNotes.text=content.main[i][1]+sources;
 if(i===1)slide.speakerNotes.text+='\n\nSynthetic example: Original: My order has not arrived. Where is it? Paraphrase 1: I am still waiting for my delivery. Paraphrase 2: Can you check the status of my missing order? Paraphrase 3: My package has not reached me yet. Twenty-five scenarios times four versions equals one hundred tickets. Different wording keeps the same basic problem and expected category.';
}
p.slides.getItem(9).speakerNotes.text=content.demo.map(([h,t])=>h+'\n'+t).join('\n\n')+sources;
await(await PresentationFile.exportPptx(p)).save(path.join(build,'candidate.pptx'));
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const final=path.join(root,'outputs/customer_support_project_presentation_final_v3_r3.pptx');
const receipt=await finalizePresentation({workspaceDir:root,candidatePath:path.join(build,'candidate.pptx'),finalPath:final,pythonExecutable:'C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit','--require-native-table-slide','3','--require-native-table-slide','7','--require-native-table-slide','8'],requiredNativeTableOwnerSlides:[3,7,8],fontPolicy:{basis:'design',families:['Arial']},verifyArtifactToolImport:true,receiptPath:path.join(build,'validation.json')});
const saved=await PresentationFile.importPptx(await FileBlob.load(final));
for(const[i,s]of saved.slides.items.entries())await fs.writeFile(path.join(build,`final-${i+1}.png`),new Uint8Array(await(await saved.export({slide:s,format:'png',scale:1})).arrayBuffer()));
await fs.copyFile(final,source);
console.log(JSON.stringify({slides:saved.slides.items.length,path:source,sha256:receipt.finalSha256}));
