/* screens/riskdata.js: placeholder stubs for the riskdata group. Every id of
   registry/riskdata.json is registered so the shell can be exercised end to end;
   the screen author replaces this file. */
(function(){
'use strict';
const NG=window.NG;
function stub(id){return function(root){NG.ui.ap(root,NG.ui.note('placeholder screen module: '+id+' (screens/riskdata.js)','neutral'))}}
NG.screen("rdm",{group:"리스크데이터",sub:null,title:"RDM",build:stub("rdm")});
NG.screen("sources",{group:"리스크데이터",sub:"RDM",title:"원천·계약",build:stub("sources")});
NG.screen("dq-recon",{group:"리스크데이터",sub:"RDM",title:"DQ·대사",build:stub("dq-recon")});
NG.screen("exceptions",{group:"리스크데이터",sub:"RDM",title:"예외·조치",build:stub("exceptions")});
NG.screen("collateral",{group:"리스크데이터",sub:"RDM",title:"담보·보증",build:stub("collateral")});
NG.screen("aggregates",{group:"리스크데이터",sub:"RDM",title:"집계 원장",build:stub("aggregates")});
NG.screen("funds",{group:"리스크데이터",sub:"선행 원장",title:"집합투자증권",build:stub("funds")});
NG.screen("derivatives",{group:"리스크데이터",sub:"선행 원장",title:"파생상품",build:stub("derivatives")});
NG.screen("securitisation",{group:"리스크데이터",sub:"선행 원장",title:"유동화",build:stub("securitisation")});
NG.screen("data-model",{group:"리스크데이터",sub:"카탈로그·코드",title:"데이터모델",build:stub("data-model")});
NG.screen("code-master",{group:"리스크데이터",sub:"카탈로그·코드",title:"코드 마스터",build:stub("code-master")});
NG.screen("code-map",{group:"리스크데이터",sub:"카탈로그·코드",title:"코드 매핑",build:stub("code-map")});
})();
