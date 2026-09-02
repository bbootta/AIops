/* screens/governance.js: placeholder stubs for the governance group. Every id of
   registry/governance.json is registered so the shell can be exercised end to end;
   the screen author replaces this file. */
(function(){
'use strict';
const NG=window.NG;
function stub(id){return function(root){NG.ui.ap(root,NG.ui.note('placeholder screen module: '+id+' (screens/governance.js)','neutral'))}}
NG.screen("validation",{group:"검증·거버넌스",sub:null,title:"검증",build:stub("validation")});
NG.screen("req-trace",{group:"검증·거버넌스",sub:"검증",title:"요건 추적",build:stub("req-trace")});
NG.screen("agents",{group:"검증·거버넌스",sub:null,title:"에이전트",build:stub("agents")});
NG.screen("kill-guard",{group:"검증·거버넌스",sub:null,title:"비상정지",build:stub("kill-guard")});
NG.screen("changes",{group:"검증·거버넌스",sub:null,title:"변경",build:stub("changes")});
NG.screen("overlay",{group:"검증·거버넌스",sub:null,title:"오버레이",build:stub("overlay")});
NG.screen("change-control",{group:"검증·거버넌스",sub:"통제",title:"변경통제",build:stub("change-control")});
NG.screen("access-sod",{group:"검증·거버넌스",sub:"통제",title:"접근통제·직무분리",build:stub("access-sod")});
NG.screen("ai-governance",{group:"검증·거버넌스",sub:"통제",title:"AI 거버넌스",build:stub("ai-governance")});
NG.screen("audit-trail",{group:"검증·거버넌스",sub:"통제",title:"실행·감사추적",build:stub("audit-trail")});
NG.screen("query-governance",{group:"검증·거버넌스",sub:"통제",title:"조회 거버넌스",build:stub("query-governance")});
})();
