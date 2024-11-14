```bash
lar -n 1 -c wcls-sig-to-img_v4.fcl -s wcsimsp_g4_gen_prodgenie_bnb_nu_cosmic_sbnd_nskip6.root -o tmp.root
python wct-img-2-bee.py "clusters-apa-apa*.gz"
```