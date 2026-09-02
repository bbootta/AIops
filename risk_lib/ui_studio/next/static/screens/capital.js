/* screens/capital.js: placeholder stubs for the capital group. Every id of
   registry/capital.json is registered so the shell can be exercised end to end;
   the screen author replaces this file. */
(function(){
'use strict';
const NG=window.NG;
function stub(id){return function(root){NG.ui.ap(root,NG.ui.note('placeholder screen module: '+id+' (screens/capital.js)','neutral'))}}
NG.screen("credit",{group:"자본·RWA",sub:null,title:"신용",build:stub("credit")});
NG.screen("ews",{group:"자본·RWA",sub:"신용",title:"조기경보",build:stub("ews")});
NG.screen("credit-rwa",{group:"자본·RWA",sub:"신용",title:"신용 RWA",build:stub("credit-rwa")});
NG.screen("ecl",{group:"자본·RWA",sub:"신용",title:"ECL",build:stub("ecl")});
NG.screen("market",{group:"자본·RWA",sub:null,title:"시장",build:stub("market")});
NG.screen("ipv",{group:"자본·RWA",sub:"시장",title:"가격검증·IPV",build:stub("ipv")});
NG.screen("backtest",{group:"자본·RWA",sub:"시장",title:"백테스팅",build:stub("backtest")});
NG.screen("var-es",{group:"자본·RWA",sub:"시장",title:"VaR·ES",build:stub("var-es")});
NG.screen("market-rwa",{group:"자본·RWA",sub:"시장",title:"시장 RWA",build:stub("market-rwa")});
NG.screen("market-portfolio",{group:"자본·RWA",sub:"시장",title:"시장 포트폴리오",build:stub("market-portfolio")});
NG.screen("portfolio-setup",{group:"자본·RWA",sub:"시장",title:"포트폴리오 설정",build:stub("portfolio-setup")});
NG.screen("oprisk",{group:"자본·RWA",sub:null,title:"운영",build:stub("oprisk")});
NG.screen("loss-recovery",{group:"자본·RWA",sub:"운영",title:"손실·회수",build:stub("loss-recovery")});
NG.screen("kri-control",{group:"자본·RWA",sub:"운영",title:"KRI·통제",build:stub("kri-control")});
NG.screen("op-rwa",{group:"자본·RWA",sub:"운영",title:"운영 RWA",build:stub("op-rwa")});
NG.screen("ncr",{group:"자본·RWA",sub:"건전성",title:"NCR·건전성",build:stub("ncr")});
})();
