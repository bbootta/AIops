/* screens/settings.js: placeholder stubs for the settings group. Every id of
   registry/settings.json is registered so the shell can be exercised end to end;
   the screen author replaces this file. */
(function(){
'use strict';
const NG=window.NG;
function stub(id){return function(root){NG.ui.ap(root,NG.ui.note('placeholder screen module: '+id+' (screens/settings.js)','neutral'))}}
NG.screen("settings",{group:"설정",sub:null,title:"설정",build:stub("settings")});
NG.screen("institution",{group:"설정",sub:"⚙ 설정",title:"기관 설정",build:stub("institution")});
NG.screen("methodology",{group:"설정",sub:"⚙ 설정",title:"산출 방법론",build:stub("methodology")});
})();
