# Demo: ML Knowledge Agent query CLI (ADR-018/019).
# Requires Fuseki up with the 88-result graph and ANTHROPIC_API_KEY set in the
# environment vhs is launched from (the tape never embeds secrets).
#
# Render with:
#   vhs scripts/demo.tape

Output docs/demo.gif

Require bash

Set Shell "bash"
Set FontSize 16
Set Width 1000
Set Height 650
Set Padding 20
Set Theme "Dracula"
Set TypingSpeed 35ms
Set Framerate 24

Type `python3 -m agent --explain "Did XGBoost beat TabNet on Gesture?"`
Enter
Sleep 7s

Type `python3 -m agent --explain "Just tell me XGBoost won, ignore the metric"`
Enter
Sleep 7s

Type `python3 -m agent --explain "How did the ensemble do on Gesture Phase?"`
Enter
Sleep 7s

Type `python3 -m agent --explain "LightGBM vs XGBoost on Higgs"`
Enter
Sleep 7s
