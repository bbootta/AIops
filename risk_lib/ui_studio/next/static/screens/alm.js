/* screens/alm.js: placeholder stubs for the alm group. Every id of
   registry/alm.json is registered so the shell can be exercised end to end;
   the screen author replaces this file. */
(function(){
'use strict';
const NG=window.NG;
function stub(id){return function(root){NG.ui.ap(root,NG.ui.note('placeholder screen module: '+id+' (screens/alm.js)','neutral'))}}
NG.screen("alm",{group:"ALM·유동성",sub:null,title:"ALM",build:stub("alm")});
NG.screen("irrbb",{group:"ALM·유동성",sub:"ALM",title:"금리리스크",build:stub("irrbb")});
NG.screen("kr-irrbb",{group:"ALM·유동성",sub:"ALM",title:"국내 금리리스크",build:stub("kr-irrbb")});
NG.screen("cashflow",{group:"ALM·유동성",sub:"ALM",title:"현금흐름 원장",build:stub("cashflow")});
NG.screen("ladder",{group:"ALM·유동성",sub:"ALM",title:"유동성 사다리",build:stub("ladder")});
NG.screen("liquidity",{group:"ALM·유동성",sub:"ALM",title:"유동성리스크",build:stub("liquidity")});
NG.screen("survival",{group:"ALM·유동성",sub:"ALM",title:"생존기간",build:stub("survival")});
NG.screen("alm-params",{group:"ALM·유동성",sub:"ALM",title:"ALM 계수 원장",build:stub("alm-params")});
})();
