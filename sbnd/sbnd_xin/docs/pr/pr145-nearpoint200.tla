# doc sbnd_xin/pr/145 sec 8 -- THE CORRECTED OPERATING POINT for the pr/129
# pointing test on the near-cross-cluster kine pool, from the owner's blind
# scan of the five refusals (sec 3.8):
#
#   impact = 200 cm  -- the test is armed by impact > 0; 200 cm places no
#                       effective bound on the observed pool (max 110.22 cm),
#                       so the direction clause decides.
#   miss_deg = 30    -- the clause that actually separates the owner's one
#                       KEEP (392009, miss 12.5 deg) from the four COSMICs
#                       (90.8 / 103.8 / 112.2 / 113.6 deg).  A 78.3 deg gap.
#
# NB this INVERTS which knob carries the physics.  At the 20 cm point priced in
# sec 3.6, miss_deg was measured INERT -- impact refused all five on its own.
# At 200 cm, miss_deg is the ONLY clause that decides.
kine_near_pointing_impact=200
kine_near_pointing_miss_deg=30
