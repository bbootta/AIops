/* screens/query.js: placeholder stubs for the query group. Every id of
   registry/query.json is registered so the shell can be exercised end to end;
   the screen author replaces this file. */
(function(){
'use strict';
const NG=window.NG;
function stub(id){return function(root){NG.ui.ap(root,NG.ui.note('placeholder screen module: '+id+' (screens/query.js)','neutral'))}}
NG.screen("structured-query",{group:"조회·컴포저",sub:null,title:"정형 조회",build:stub("structured-query")});
NG.screen("adaptive-ui",{group:"조회·컴포저",sub:null,title:"비정형 UI",build:stub("adaptive-ui")});
})();
