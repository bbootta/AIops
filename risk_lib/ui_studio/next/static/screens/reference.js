/* screens/reference.js: placeholder stubs for the reference group. Every id of
   registry/reference.json is registered so the shell can be exercised end to end;
   the screen author replaces this file. */
(function(){
'use strict';
const NG=window.NG;
function stub(id){return function(root){NG.ui.ap(root,NG.ui.note('placeholder screen module: '+id+' (screens/reference.js)','neutral'))}}
NG.screen("commercial",{group:"(참고)",sub:null,title:"상업성",build:stub("commercial")});
})();
