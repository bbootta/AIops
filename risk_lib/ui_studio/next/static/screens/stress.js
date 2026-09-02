/* screens/stress.js: placeholder stubs for the stress group. Every id of
   registry/stress.json is registered so the shell can be exercised end to end;
   the screen author replaces this file. */
(function(){
'use strict';
const NG=window.NG;
function stub(id){return function(root){NG.ui.ap(root,NG.ui.note('placeholder screen module: '+id+' (screens/stress.js)','neutral'))}}
NG.screen("stress",{group:"위기상황·ICAAP",sub:null,title:"위기상황",build:stub("stress")});
NG.screen("macro",{group:"위기상황·ICAAP",sub:"위기상황",title:"거시지표 모니터링",build:stub("macro")});
NG.screen("scenario",{group:"위기상황·ICAAP",sub:"위기상황",title:"시나리오 설정",build:stub("scenario")});
NG.screen("reverse-stress",{group:"위기상황·ICAAP",sub:"위기상황",title:"역스트레스",build:stub("reverse-stress")});
NG.screen("icaap",{group:"위기상황·ICAAP",sub:"위기상황",title:"ICAAP 인벤토리",build:stub("icaap")});
NG.screen("actions",{group:"위기상황·ICAAP",sub:"위기상황",title:"경영조치·제출",build:stub("actions")});
})();
