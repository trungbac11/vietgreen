const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const context = {Intl, URLSearchParams, Number, Math, String, encodeURIComponent,
  esc: v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
  fmt: v => new Intl.NumberFormat('en-US',{maximumFractionDigits:3}).format(Number(v))};
vm.createContext(context);
vm.runInContext(fs.readFileSync('app/static/overview.js','utf8'), context);
const insight = {company_id:'C1',metric_id:'water',entity:'site',boundary:'plant',unit_id:'m3',measurement_type:'actual',from_year:2022,to_year:2023,from_value:100,to_value:80,unit_code:'m³',change_percent:-20,sources:[{source_file:'report.pdf',page:'12'}]};
context.insight = insight;
assert.match(vm.runInContext('pairChart(insight)',context), /2022: 100; 2023: 80 m³/);
assert.match(vm.runInContext('insightHref(insight)',context), /metric=water.*entity=site.*boundary=plant.*unit=m3.*type=actual/);
assert.match(vm.runInContext('insightSource(insight)',context), /report\.pdf, PDF p\. 12/);
assert.equal(vm.runInContext('direction(insight)',context), 'Decrease');
assert.equal(vm.runInContext('pct(78.81234)',context), '78.8');
console.log('PASS: overview chart values, source, scope drill-down and percentage formatting');
