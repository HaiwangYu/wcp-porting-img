# separate the original wire-cell computing graph configuration into 3
- original wcls-img-clus-matching.jsonnet needs to run with larsoft enviroment (lar -c xxx.fcl), now I want to separate it into 3 tasks, with the IO part still run in larsoft, but the core algorithms run in standalone wire-cell
- the Origin graph is in wcls-img-clus-matching.jsonnet and run with wcls-img-clus-matching.fcl, page 1 "current" of the pdf described it in sense of main logics/IO
- the wanted separated configurations are described in page 2 "plan" of the pdf. In this page, I want the A, B, C part implemented.
- write all the new configurations (jsonnet, fcl) in this folder `/exp/sbnd/app/users/yuhw/wcp-porting-img/sbnd/standalone-sample/`
- reference: `/exp/sbnd/app/users/yuhw/wcp-porting-img/sbnd` and `/exp/sbnd/app/users/yuhw/sbnd-op`
- ask me if anyting is not clear
- do not auto-commit