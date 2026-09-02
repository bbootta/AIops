/* screens/control.js: placeholder stubs for the control group. Every id of
   registry/control.json is registered so the shell can be exercised end to end;
   the screen author replaces this file. */
(function(){
'use strict';
const NG=window.NG;
function stub(id){return function(root){NG.ui.ap(root,NG.ui.note('placeholder screen module: '+id+' (screens/control.js)','neutral'))}}
NG.screen("cockpit",{group:"통제센터",sub:null,title:"콕핏",build:stub("cockpit")});
NG.screen("decision-queue",{group:"통제센터",sub:null,title:"의사결정 큐",build:stub("decision-queue")});
NG.screen("close-workflow",{group:"통제센터",sub:null,title:"마감 워크플로",build:stub("close-workflow")});
NG.screen("simulation",{group:"통제센터",sub:null,title:"시뮬레이션",build:stub("simulation")});
NG.screen("limits",{group:"통제센터",sub:"한도·거액",title:"한도관리",build:stub("limits")});
NG.screen("lex-setting",{group:"통제센터",sub:"한도·거액",title:"거액 설정",build:stub("lex-setting")});
NG.screen("lex-analysis",{group:"통제센터",sub:"한도·거액",title:"거액 분석",build:stub("lex-analysis")});
})();
