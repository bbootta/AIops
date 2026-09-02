/* screens/reports.js: placeholder stubs for the reports group. Every id of
   registry/reports.json is registered so the shell can be exercised end to end;
   the screen author replaces this file. */
(function(){
'use strict';
const NG=window.NG;
function stub(id){return function(root){NG.ui.ap(root,NG.ui.note('placeholder screen module: '+id+' (screens/reports.js)','neutral'))}}
NG.screen("exec-report",{group:"보고서",sub:null,title:"종합보고서",build:stub("exec-report")});
NG.screen("approval-pack",{group:"보고서",sub:null,title:"결재 패키지",build:stub("approval-pack")});
NG.screen("headline-trend",{group:"보고서",sub:null,title:"헤드라인 추이",build:stub("headline-trend")});
NG.screen("capital-verdict",{group:"보고서",sub:null,title:"자본 판정",build:stub("capital-verdict")});
NG.screen("reg-forms",{group:"보고서",sub:null,title:"감독보고",build:stub("reg-forms")});
})();
