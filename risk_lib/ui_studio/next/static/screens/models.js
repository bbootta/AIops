/* screens/models.js: placeholder stubs for the models group. Every id of
   registry/models.json is registered so the shell can be exercised end to end;
   the screen author replaces this file. */
(function(){
'use strict';
const NG=window.NG;
function stub(id){return function(root){NG.ui.ap(root,NG.ui.note('placeholder screen module: '+id+' (screens/models.js)','neutral'))}}
NG.screen("model-inventory",{group:"모형",sub:null,title:"모형 인벤토리",build:stub("model-inventory")});
NG.screen("validation-schedule",{group:"모형",sub:"모형 인벤토리",title:"검증 일정",build:stub("validation-schedule")});
NG.screen("model-risk",{group:"모형",sub:"모형 인벤토리",title:"모형리스크",build:stub("model-risk")});
NG.screen("model-lifecycle",{group:"모형",sub:"모형 인벤토리",title:"모형 수명주기",build:stub("model-lifecycle")});
NG.screen("performance",{group:"모형",sub:"신용모형",title:"변별력·안정성",build:stub("performance")});
NG.screen("calibration",{group:"모형",sub:"신용모형",title:"등급 보정",build:stub("calibration")});
NG.screen("migration",{group:"모형",sub:"신용모형",title:"등급 전이",build:stub("migration")});
NG.screen("pd-estimate",{group:"모형",sub:"내부등급법 추정",title:"PD 추정",build:stub("pd-estimate")});
NG.screen("lgd-estimate",{group:"모형",sub:"내부등급법 추정",title:"LGD 추정",build:stub("lgd-estimate")});
NG.screen("ccf-estimate",{group:"모형",sub:"내부등급법 추정",title:"CCF 추정",build:stub("ccf-estimate")});
NG.screen("capm-discount",{group:"모형",sub:"내부등급법 추정",title:"회수 할인율",build:stub("capm-discount")});
NG.screen("defaulted-lgd",{group:"모형",sub:"내부등급법 추정",title:"부도자산 LGD",build:stub("defaulted-lgd")});
NG.screen("beel-plgd",{group:"모형",sub:"내부등급법 추정",title:"BEEL·PLGD",build:stub("beel-plgd")});
NG.screen("irb-governance",{group:"모형",sub:"내부등급법 추정",title:"모형 거버넌스",build:stub("irb-governance")});
NG.screen("lgd-ead-backtest",{group:"모형",sub:"내부등급법 추정",title:"LGD·EAD 실측검증",build:stub("lgd-ead-backtest")});
NG.screen("behaviour-model",{group:"모형",sub:"고객행동모형",title:"행동모형 추정",build:stub("behaviour-model")});
NG.screen("nmd-core",{group:"모형",sub:"고객행동모형",title:"비만기성예금 코어",build:stub("nmd-core")});
NG.screen("behaviour-backtest",{group:"모형",sub:"고객행동모형",title:"행동모형 백테스트",build:stub("behaviour-backtest")});
})();
