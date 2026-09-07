# doc sbnd_xin/pr/146 -- arm C of the stray-satellite classifier is the only
# drop arm with NO direction test: it drops a track-like satellite purely for
# BEING a straight continuation of a known track.  That is the signature of a
# fragment of the candidate's own muon.  This waives arm C when the satellite
# aims at the main vertex within 45 deg -- the SAME threshold arm B already
# uses (kine_sat_angle_main), reused rather than fitted.
#
# C++ default is 0.0 = no waiver = byte-identical legacy.
#
# Consumed by run_pr_chain_batch.sh via PR_EXTRA_TLA (--tla-code, NOT -A:
# -A passes a STRING and "0" != 0 in jsonnet, which silently defeats the
# key-suppression idiom).
kine_sat_cont_keep_deg=25
