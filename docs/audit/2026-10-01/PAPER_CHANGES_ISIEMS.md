<div dir="rtl">

# הצעות שינוי: מאמר ISIEMS v3 מול הרשומה

תאריך: 2026-10-01. הרשומה: commit `27211b3` (טבלאות `outputs/tables/*_req_soft3.csv`, ‏`outputs/check_results/logo_*_req_soft3_relwls_quad.csv`, ‏`cfd_vs_kb_ufc215.csv`, ‏`data/free_field_data.csv`) ו־`7b8fb1a` (`validation_comparison_req_soft3.csv`). כל הערכים נקראו ב־`git show <commit>:<path>`.
המאמר: `isiems_paper/ISIEMS Paper v3.pdf` (קריאה בלבד). בסיס: `TRACEABILITY_ISIEMS_v3.md` (אותה תיקייה), 18 קבוצות משפטים לא נתמכים.
**הצעות בלבד.** שום קובץ מלבד זה לא נערך. המשפטים המוצעים באנגלית, במשלב המאמר; הבעלים מחליט.
סקריפטים (מחוץ לריפו): scratchpad `claims/claims.py`, ‏`claims/claims2.py`, פלט ב־`claims_out.txt`, ‏`claims2_out.txt`. LOGO צולב ותיבה בטוחה: scratchpad `logo_check/cross_logo.py`, ‏`logo_check/safe_box.py`.

## שיטות (שיטה אחת לכל בדיקה)

סימון: Z_conv = R_conv/W^1/3 מ־`convergence_table_req_soft3.csv` (`RadiusP`, `RadiusI`, `ChargeWeight`). ‏ρ=`AreaDensity`, ‏s̃=s/W^1/3, ‏H/s.

- **3a, דירוג חמשת הקלטים.** ליבה = תצורות 1–72. אין הגדרה כתובה בריפו; המאמר (עמ' 4) מגדיר אותה כגוש המאוזן 2·2·3·3·2, ונבדק שתצורות 1–72 הן בדיוק המכפלה המלאה (det {1,2}, b {15,30}, s {5,20}, H {4,12,24}, W {50,500,1500}; 72 צירופים שונים). מדד ראשי: חציון |Δ ln Z_conv| על כל זוגות התצורות שנבדלים בקלט אחד בדיוק (36 זוגות לקלט בן 2 רמות, 72 לקלט בן 3 רמות; כל הזוגות, לא רק שכנים). בדיקה: ANOVA של אפקטים ראשיים על ln Z_conv, ‏η²p = SS_f/(SS_f+SS_E), בחישוב ידני ב־numpy (statsmodels לא מותקן). בנוסף: חלק השונות של כל אינטראקציה דו־כיוונית.
- **3b, סימן dZ_conv/d(H/s).** סדרה = תצורות ליבה עם (det, b, s, W) קבועים ו־H משתנה: **24 סדרות** של 3 גבהים. שיפוע = ריבועים פחותים של Z_conv על H/s (כמו `slope` ב־`make_fig3_16x9_v2.m`); בנוסף 48 צעדים עוקבים (4→12, 12→24). s̃<1: ‏8 סדרות (s=5, ‏W=500,1500), ‏s̃>1: ‏16.
- **3c, Λ_P>1.** ‏Λ = `MaxR`/`R_free` מ־`max_radius_per_Z_req_soft3.csv`. שורות: `z_urban_valid_mask` (`blastlib/regression/z_urban.py:216`): ‏beyond=False, ‏R_free<R_conv, ‏R_free>`ExcludeR`, ‏Z≥2. ‏685 שורות P, ‏1020 שורות I, מכל 96 התצורות. כלל לתצורה: מוגברת אם חציון Λ_P בשורותיה >1 (כלל הרוב נותן אותו דבר ב־s̃<1). להשוואה גם "beyond בלבד" (841 / 1156 שורות, השיטה של ה־trace).
- **3d, β מתוקננים.** OLS של ln Z_conv,I על רגרסורי Eq.(8): ‏ln ρ, ‏ln(H/s), ‏ln s̃, ‏ln²s̃, לכל det בנפרד (48 תצורות), מנבאים ותגובה מתוקננים (z-score). בנוסף ΔR² בהשמטת קבוצת משתנה (ל־s̃: שני האיברים יחד), כי ln s̃ ו־ln²s̃ מתואמים.
- **3e, Fig.4.** ‏Fig.4 של המאמר נוצרת מ־`isiems_paper/make_fig3_16x9_v2.m` (לא הורץ), שקורא `outputs/tables/convergence_table_req_soft3.csv` מעץ העבודה (זהה ל־`27211b3`). ‏(a)–(c): ‏R_conv,P [מ'] מול H, ‏det1, ‏W=50/500/1500, ארבעה קווים (s 5/20 × B 15/30); ‏(d)–(f): אותו ל־R_conv,I; ‏(g),(h): שיפוע dZ_conv/d(H/s) מול s̃ ל־24 הסדרות. הערכים שוחזרו ב־scratch מהלוגיקה של הסקריפט, מול `430d004` (שתואם את ה־PDF) ומול הרשומה.
- **4, ‏KB.** מ־`outputs/check_results/cfd_vs_kb_ufc215.csv` (הטבלה המלאה של `cfd_vs_kb_ufc_note.md`, ‏UFC 3-340-02 Fig. 2-15). פער = CFD/KB − 1, ממוצע על חמשת המשקלים, ב־Z שלמים; רצועות כוללות קצוות.

## תוצאות 3a–3e ו־4

### 3a דירוג (ליבה, 72)

| קלט | P: חציון \|Δ ln Z\| | P: η²p | I: חציון \|Δ ln Z\| | I: η²p |
|---|---|---|---|---|
| s | **0.153 (1)** | 0.177 (2) | **0.244 (1)** | **0.651 (1)** |
| H | 0.123 (2) | 0.009 (5) | 0.147 (2) | 0.452 (2) |
| W | 0.101 (3) | 0.065 (4) | 0.111 (4) | 0.422 (3) |
| det | 0.087 (4) | 0.093 (3) | 0.049 (5) | 0.092 (5) |
| b | 0.071 (5) | **0.190 (1)** | 0.122 (3) | 0.323 (4) |

- רוחב הרחוב ראשון או שני בשני הגדלים ובשתי השיטות: **נתמך**.
- "For peak overpressure, the charge weight was ranked first": **לא נתמך** (W שלישי/רביעי).
- אי־הסכמה בין השיטות ב־P: ‏b ראשון ב־η²p ואחרון בחציון הצעדים; ‏H שני בצעדים ואחרון ב־η²p. הסיבה: אפקטי H ו־b מתהפכים (אינטראקציות s×H ‏14.2% ו־b×W ‏12.6% מהשונות). ב־I הסדר יציב: s, H בראש, b/W מתחלפים במקום 3–4, det אחרון.
- ב־P האפקטים הראשיים מסבירים 38.6% מהשונות של ln Z_conv,P ואינטראקציות דו־כיווניות 36.1%: **תומך** ב־"the interactions ... are as large as the effects of each input alone". ב־I: ‏80.0% מול 14.5%.
- "For impulse, it acts mainly through its interaction with the street width": אינטראקציית W×s היא 1.7% מהשונות של ln Z_conv,I, מול אפקט ראשי של W ‏14.6% (η²p ‏0.42). במובן הסטטיסטי **לא נתמך**. במובן הפיזיקלי (בגיאומטריה קבועה W משנה רק את s̃) זה נכון מעצם ההגדרה של קנה המידה.

### 3b סימן dZ_conv/d(H/s) (24 סדרות ליבה)

| | P: סדרות שליליות/חיוביות | P: חציון שיפוע | P: צעדים −/+ | I: סדרות −/+ | I: חציון שיפוע | I: צעדים −/+ |
|---|---|---|---|---|---|---|
| s̃<1 (8) | 0/8 | +0.71 | 1/15 | 0/8 | +1.10 | 0/16 |
| s̃>1 (16) | 14/2 | −0.90 | 27/5 | 4/12 | +2.00 | 8/24 |

- P: ההיפוך ב־s̃=1 **נתמך** ("in nearly every case" = ‏14/16; החריגות: det2 B30 W50 בשני רוחבי הרחוב, ‏+0.14 ו־+0.49).
- I: "no such reversal occurs at any street width" **לא נתמך מילולית**: 4/16 סדרות שליליות, ושלוש מהן ב־s̃=5.43 (s=20, ‏W=50: det1 B15 ‏−2.84, ‏det2 B15 ‏−1.32, ‏det2 B30 ‏−2.74); הרביעית det1 B15 W500 (s̃=2.52, ‏−0.45). בחציון השיפוע חיובי בשני המשטרים (‏+1.10, ‏+2.00).

### 3c שיעור ההגברה Λ_P>1

| | שורות (valid mask) | תצורות (חציון >1) | שורות (beyond בלבד) | תצורות (beyond בלבד) |
|---|---|---|---|---|
| s̃<1 | 78.7% (267 שורות) | **32/36 = 88.9%** | 72.0% | 32/36 = 88.9% |
| s̃>1 | 40.4% (418) | 25/60 = 41.7% | 43.0% | 26/60 = 43.3% |

- "roughly 75% of the configurations": בתצורות 89%. ‏75% מתאים רק לחלק **השורות** (72–79%). המשפט צריך תיקון.
- s̃>1: חציון חציוני התצורות 0.976; "amplification ceases to be systematic": **נתמך**.
- חציון Λ על השורות: ‏valid mask ‏P 1.014 / I 1.277; ‏beyond בלבד 1.012 / 1.284. ‏Λ_I>1 בחציון ב־91/96 תצורות (valid).

### 3d β מתוקננים, ln Z_conv,I (רגרסורי Eq.8)

| det | R² | β ln ρ | β ln(H/s) | β ln s̃ | β ln²s̃ | ΔR² בלי ρ | ΔR² בלי H/s | ΔR² בלי s̃ (שניהם) |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.825 | **+0.723** | +0.567 | +0.488 | −0.213 | **0.280** | 0.193 | 0.072 |
| 2 | 0.815 | +0.773 | +0.696 | **+0.862** | −0.128 | **0.321** | 0.291 | 0.292 |

- "depends mainly on ρ": נתמך ב־det1 (שני המדדים). ב־det2 ‏β של ln s̃ (0.86) גדול מ־ρ (0.77), ו־ΔR² של שלושת הפרמטרים כמעט שווה (0.32/0.29/0.29). **נתמך חלקית**. ‏"A denser layout ... gives a larger radius": ‏β_ρ חיובי בשניהם, **נתמך**.
- להשוואה, אותה רגרסיה ל־ln Z_conv,P: ‏R² ‏0.30 (det1) / 0.27 (det2): **תומך** ב־"no smooth power law describes the radius" ללחץ.

### 3e ‏Fig.4 (a–f): ה־PDF מול הרשומה (‏det1, ‏R_conv [מ'] ב־H=4/12/24)

| פאנל | ב־PDF (= `430d004`) | ברשומה `27211b3` |
|---|---|---|
| (a) P, ‏W=50 | s5B15 28.3/28.3/24.3; s5B30 31.3/36.7/30.5; s20B15 26.1/26.1/26.1; s20B30 32.7/32.5/31.7 | 33.0/33.1/29.5; **45.5/43.8/38.7** (יורד במקום שיא ב־H=12); 29.9/29.8/29.7; 35.9/35.4/34.4 |
| (b) P, ‏W=500 | 69.0/80.5/92.0; 66.5/72.4/93.4; 78.4/64.9/60.6; 73.8/61.7/59.5 | 72.3/83.7/94.6; 76.7/83.2/99.6; 83.0/67.9/61.8; 88.2/71.2/68.8 (אותה צורה, ‏+3 עד +14 מ') |
| (c) P, ‏W=1500 | 103.2/100.4/113.9; 91.7/96.2/119.8; 106.1/102.8/92.3; 105.1/96.2/99.5 | 106.0/104.0/115.7; 100.4/104.8/128.8; 111.5/106.0/93.1; 119.9/104.6/104.6 |
| (d) I, ‏W=50 | 51.1/53.1/51.6; 49.2/53.7/56.2; 32.9/33.0/33.0; 36.7/36.7/37.6 (כמעט שטוח) | 60.2/72.3/71.7; **71.4/89.3/107.6**; 53.9/47.1/**43.1** (יורד); 54.4/59.9/62.3 |
| (e) I, ‏W=500 | 101.6/103.0/107.6; 112.4/113.8/119.6; 79.7/80.7/80.8; 84.1/86.5/85.6 | 123.7/142.7/154.3; 132.5/149.6/173.9; 94.5/102.7/92.1; 103.0/118.2/120.9 |
| (f) I, ‏W=1500 | 109.2/111.6/122.2; 153.6/153.9/162.2; 120.7/121.2/120.8; 139.6/140.2/140.5 | 171.6/195.9/209.3; 173.3/206.9/**223.6**; 123.1/160.2/162.1; 141.2/175.1/180.4 |
| (g) P | טווח −2.56…+0.87; ‏s̃<1 ‏8/8 חיוביים; ‏s̃>1 ‏15/16 שליליים | −2.56…+0.93; ‏8/8; ‏14/16 |
| (h) I | 0.00…+2.48, אין ערך שלילי | **−2.83…+4.06**; ‏8/8 חיוביים ב־s̃<1; ‏4/16 שליליים ב־s̃>1 |

- שורה P: אותה צורה, ערכים גבוהים ב־3–14 מ' (‏(a) s5B30 משנה צורה). שורה I: שינוי איכותי. במקום קווים כמעט שטוחים יש עלייה ברורה עם H (עד +50 מ' ב־(f)), וב־s20B15 ‏W=50 ירידה.
- הקובץ `isiems_paper/images/PS_Fig3_16x9_v2.png` (‏2026-10-01 11:30) כבר מציג את ערכי הרשומה (נבדק בעין: (a) 45.5/43.8/38.7, ‏(f) עד ≈224). ה־PDF של v3 לא מכיל אותו.
- Fig.5: ציר R_conv,I ב־PDF מגיע עד 180 מ'. ברשומה הערך הנמדד המקסימלי 224.7 מ' (מנובא 222.8), כך שהציר חייב להשתנות (`PS_Fig4.png` של 10-01 כבר מעודכן).

### 4 ‏CFD מול Kingery-Bulmash (UFC 3-340-02 Fig. 2-15)

| רצועת Z [m/kg^1/3] | לחץ שיא: טווח (חציון) | לחץ: קצוות לפי W | אימפולס מקונ"מ: טווח (חציון) |
|---|---|---|---|
| 2–8 | −7.0% עד −9.4% (‏−8.0%) | −2.7% עד −20.3% | −8.5% עד −16.7% (‏−9.9%; ‏−16.7 רק ב־Z=2) |
| 8–12 | −8.2% עד −18.1% (‏−14.0%) | −3.7% עד −23.1% | −10.8% עד −12.3% (‏−11.6%) |
| 12–20 | −18.1% עד −30.5% (‏−26.0%) | −11.1% עד −35.0% | −12.0% עד −12.6% (‏−12.4%) |
| 20–30 | רק Z=20: ‏−30.5% | −26.4% עד −35.0% | רק Z=20: ‏−12.6% |

Z>20 **לא מכוסה** (`free_field_data.csv` וטבלת KB מסתיימות ב־Z=20). הסימן שלילי בכל מקום: ה־CFD נמוך מ־KB. הפער בלחץ גדל עם המרחק, ובאימפולס כמעט קבוע (כ־12%).

### בדיקת ערך רצפת D35 (מ־`free_field_data.csv`)

Z שבו P_ff=10 kPa (אינטרפולציה log-log) ו־I_ff/W^1/3 שם: ‏W=50: ‏11.33, ‏24.33; ‏250: ‏11.97, ‏22.99; ‏500: ‏12.13, ‏21.87; ‏1000: ‏11.27, ‏24.32; ‏1500: ‏11.27, ‏24.41. ממוצע Z ‏11.59, ממוצע רצפה **23.58 ≈ 23.6** Pa·s/kg^1/3 (= kPa·ms/kg^1/3). תואם את D35 (21.9–24.4).

## הטבלה הראשית: משפטים לא נתמכים והצעות

מספור 1–18 לפי `TRACEABILITY_ISIEMS_v3.md`. ‏19–26 נמצאו בבדיקות 3a–3e או בבדיקת Eq.(3). "עמוד" = מספר העמוד המודפס ב־PDF.

| # | עמוד | המשפט כפי שהודפס | משפט מוצע | מקור |
|---|---|---|---|---|
| 1 | 7 | "The median scaled radius Zconv is 9.0 m/kg1/3 for peak overpressure and 11.6 m/kg1/3 for impulse." | "The median scaled radius Z_conv is 9.9 m/kg^1/3 for peak overpressure and 16.2 m/kg^1/3 for impulse." | `convergence_table_req_soft3.csv`, ‏`RadiusP`/`RadiusI`/W^1/3: חציון 9.907 / 16.226 |
| 2 | 7 | "At the median, the impulse radius is therefore about 1.3 times the peak overpressure radius (11.6/9.0)." | "At the median, the impulse radius is therefore about 1.6 times the peak overpressure radius (16.2/9.9)." | אותו קובץ: 1.638 (חציון היחסים 1.65) |
| 3 | 7 | "Over all 96 configurations, the scaled radius in peak overpressure does not exceed 13 m/kg1/3." | "Over all 96 configurations, the scaled radius in peak overpressure does not exceed 15 m/kg^1/3 (largest value 14.7 m/kg^1/3)." | מקסימום 14.695 (config_58); 3 מעל 13 |
| 4 | 7 | "In impulse it exceeds 16 m/kg1/3 in two configurations only, and its largest value is 21.5 m/kg1/3." | "In impulse it exceeds 20 m/kg^1/3 in eight configurations, and its largest value is 29.2 m/kg^1/3." | 51 מעל 16; ‏8 מעל 20 (22, 25, 26, 40, 43, 58, 61, 62); מקסימום 29.210 (config_25). הערה: 8 אלה מעבר לטווח Z≤20 של `free_field_data.csv` |
| 5 | 7 | "In peak overpressure this bound follows from the 10 kPa floor of Equation (2), which the free-field overpressure reaches at a slightly smaller scaled distance." | "In both quantities the floor lies on the same free-field contour, Z ≈ 11.6 m/kg^1/3. The peak-overpressure radius exceeds it in 13 configurations, whereas the impulse radius exceeds it in 95, since the amplified impulse remains above its floor farther out." | Z_conv,P>11.6: ‏13; ‏Z_conv,I>11.6: ‏95; ‏Λ_I>1 ב־91/96 (3c); D35 |
| 6 | 7 | "No such floor applies in impulse, and its radius extends farther." | "The impulse radius exceeds the peak-overpressure radius in all 96 configurations." | Z_I>Z_P ב־96/96. החלק "No such floor" סותר את D35 |
| 7 | 5 | Eq.(3): "\|i-iff\|/W^1/3 < 20 kPa·ms/kg^1/3" | Eq.(3): "\|i/i_ff − 1\| ≤ 10%  or  i/W^1/3 < 23.6 kPa·ms/kg^1/3" | `blastlib/constants.py` `IMPULSE_CRITERION` (`rel_band=0.10`, `floor_scaled=23.6`); DECISIONS D35 (c). ‏1 kPa·ms = 1 Pa·s |
| 8 | 4 | "...and the impulse tolerance was set on the scaled impulse. Its value is the smallest for which a radius was obtained in every configuration." | "...whereas the impulse tolerance was set as a relative band of 10%, twice the impulse tolerance of the mesh study, which is invariant under the scaling. Its floor was set on the scaled impulse: 23.6 kPa·ms/kg^1/3 is the scaled free-field impulse at the scaled distance where the free-field overpressure is 10 kPa (Z ≈ 11.6 m/kg^1/3), averaged over the five charge weights (21.9–24.4)." | D35 ("עוגן", "ערך הרצפה"); הערת `rel_band` ב־`constants.py` (‏10% = פעמיים 5%); חישוב: 21.87–24.41, ממוצע 23.58 ב־Z ממוצע 11.59. הנימוק המודפס הוא של D22 |
| 9 | 4 | "In peak overpressure, a second clause was added: a floor below which the urban overpressure itself is too weak to matter structurally." | "In both quantities, a second clause was added: a floor below which the urban load itself is too weak to matter structurally." | D35: רצפה גם באימפולס |
| 10 | 5–6 | "The smoothed criterion returns a radius that is approximately 17% larger at the median, which is on the safe side for protective design." | "The smoothed criterion returns a radius that is approximately 10% larger at the median (20% at the 90th percentile), although in six configurations it is smaller." | **נמדד על `27211b3` (2026-10-01):** ‏(R_P soft β=3 − R_P hard)/R_P hard, כל 96 התצורות: חציון +10.44%, ‏p90 ‏+20.11%, ממוצע +11.43%, מקסימום +66.86% (config_95), מינימום −13.24% (config_55), שלילי ב־6. שיטה: `run_analysis.py --phase 1 --no-figures` על `data/raw_npz`, פעם `--radius-method req` ופעם `req_soft3`, ל־scratch; ריצת ה־soft משחזרת את `convergence_table_req_soft3.csv` של הרשומה (max\|Δ\| = 0); ‏RadiusI זהה בשתיהן. (D4 על `53b280c`: ‏+10.05 / +19.34 / −13.25.) scratchpad `inflation/` |
| 11 | 6 | "Expressed through the amplification factor of Equation (6), the median is 0.995 in peak overpressure against 1.261 in impulse." | "Expressed through the amplification factor of Equation (6), the median within the convergence radius is 1.01 in peak overpressure against 1.28 in impulse." | `max_radius_per_Z_req_soft3.csv`, ‏Λ=`MaxR_*`/`R_free`, שורות `z_urban_valid_mask`: ‏1.014 / 1.277 (685/1020 שורות); ‏beyond בלבד: 1.012 / 1.284 |
| 12 | 7 | "For peak overpressure, the charge weight was ranked first." | **נוסח הבעלים (2026-10-01):** "For peak overpressure, no single ranking holds: the street width is among the most influential inputs, and the interactions (s×H, b×W) are as large as the main effects." | 3a: שתי השיטות לא מסכימות (חציון צעדים s > H > W > det > b; ‏η²p b > s > det > W > H); אפקטים ראשיים 38.6% מול אינטראקציות דו־כיווניות 36.1%; W שלישי (חציון צעדים 0.101) / רביעי (η²p 0.065); s×H ‏14.2%, ‏b×W ‏12.6% |
| 13 | 7 | "Among the three parameters of Equation (1), the impulse radius depends mainly on the plan-area density ρ, and the dependence is like a smooth power law." | **נוסח הבעלים (2026-10-01):** "Among the three parameters of Equation (1), the impulse radius depends mainly on ρ and s̃, and the dependence is like a smooth power law." | לתשומת לב: ב־det1 ‏ΔR² של H/s ‏(0.19) גדול משל s̃ ‏(0.07). 3d: ‏det1 β_ρ 0.72 (ΔR² 0.28); det2 β 0.77/0.86/0.70, ‏ΔR² 0.32/0.29/0.29; ‏R² ‏0.83/0.82 |
| 14a | 8 | Table 2, Eq.(7) det1: "9.063 -0.645 2.018 0.591 1" | "10.139 −0.762 2.423 0.418 1" | `final_production_convergence_coefficients_req_soft3.csv`, ‏Det=1, ‏RadiusP: ‏`C0, C1_sW13, C2_switch, C3_canyon, a_thresh` |
| 14b | 8 | Table 2, Eq.(7) det2: "11.858 -1.375 2.782 0.776 2" | "11.605 −0.776 1.926 0.648 2" | אותו קובץ, Det=2, RadiusP |
| 14c | 8 | Table 2, Eq.(8) det1: "14.936 0.203 0.024 0.065 -0.101" | "20.486 0.274 0.112 0.119 −0.046" | Det=1, RadiusI: ‏`A, p_rho, q_HoverS, r_sW13, r2_sW13sq` |
| 14d | 8 | Table 2, Eq.(8) det2: "14.602 0.176 0.079 0.125 -0.089" | "20.926 0.292 0.137 0.209 −0.028" | Det=2, RadiusI |
| 15 | 7–8 | Fig.4 (a)–(f) ו־(g, h): ערכי R_conv וערכי השיפוע | להחליף את התמונה ב־`images/PS_Fig3_16x9_v2.png` (‏10-01, כבר מהרשומה). הכיתוב יכול להישאר. | 3e; `convergence_table_req_soft3.csv`; `make_fig3_16x9_v2.m` |
| 16a | 9 | Fig.5(a): "R² = 0.941, MAPE = 8.4 %, median error = 5.7 %, 90th percentile = 18.7 %, 62 of 96 within ±10 %, 89 of 96 within ±20 %" | "R² = 0.924, MAPE = 9.4 %, median error = 6.7 %, 90th percentile = 20.9 %, 59 of 96 within ±10 %, 85 of 96 within ±20 %" | `logo_cv_req_soft3_relwls_quad.csv`, ‏Target=P, ‏R² על R במטרים (לוגיקת `make_fig4.py`); מקסימום 38.46 (config_58) |
| 16b | 9 | Fig.5(b): "R² = 0.926, MAPE = 7.2 %, median error = 5.9 %, 90th percentile = 16.4 %, 68 of 96 within ±10 %, 90 of 96 within ±20 %" | "R² = 0.951, MAPE = 7.1 %, median error = 4.8 %, 90th percentile = 17.9 %, 78 of 96 within ±10 %, 86 of 96 within ±20 %" | Target=I; מקסימום 31.13 (config_52). ציר 180 מ' קטן מ־224.7 מ' הנמדד |
| 17 | 8 | "A supporting test, with 500 random splits of the configurations, returned median errors of 8.8% in peak overpressure and 7.2% in impulse." | "A supporting test, with 500 random splits of the configurations, returned median errors of 9.6% in peak overpressure and 6.8% in impulse." | `cv_summary_req_soft3.csv` (500 שורות), חציון `conv_P` 9.596, ‏`conv_I` 6.843 |
| 18 | 3 | "The free-field predictions of the solver agree with Kingery and Bulmash to within approximately 10% in peak overpressure [18]." | **נוסח הבעלים (2026-10-01):** "The solver's free-field overpressure lies 8% below Kingery-Bulmash at Z = 2–8, increasing to 26% at Z = 12–20; the impulse lies 10–12% below. Each urban run is compared with its own reference run, so the ratios reflect the buildings alone; beyond R_conv, the Kingery-Bulmash values are therefore conservative." | `cfd_vs_kb_ufc215.csv` (סעיף 4): חציוני לחץ −8.0 / −14.0 / −26.0%, אימפולס −9.9 / −11.6 / −12.4%. אם ההפניה [18] נשארת, יש להפריד בין טענת הספרות לבין ההשוואה של הריצות האלה |
| 19 | 5 | "The floor is anchored in the quantity-distance scale of the International Ammunition Technical Guidelines (IATG) [19], the level below which average damage to unstrengthened buildings remains limited." | "The pressure floor is anchored in the quantity-distance scale of the International Ammunition Technical Guidelines (IATG) [19], the level below which average damage to unstrengthened buildings remains limited; the impulse floor is the scaled free-field impulse on the same contour." | D35 ("אותה רמת IATG") |
| 20 | 7 | "For impulse, it acts mainly through its interaction with the street width, through s̃." | "For impulse, it ranks third or fourth; at fixed geometry it acts only through s̃, as the scaling requires." | 3a: ‏W×s ‏1.7% מהשונות של ln Z_conv,I; אפקט ראשי של W ‏14.6% (η²p 0.42) |
| 21 | 7 | "For s̃ < 1 m/kg1/3, the peak overpressure was amplified in roughly 75% of the configurations." | **נוסח הבעלים (2026-10-01):** "For s̃ < 1 m/kg^1/3, the peak overpressure was amplified in about 80% of the rows (32 of 36 configurations)." | 3c: שורות 78.7% (valid mask, ‏267 שורות); ‏32/36 = 88.9% (valid mask וגם beyond בלבד); 75% מתאים רק לחלק השורות (72–79%) |
| 22 | 7 | "In impulse, no such reversal occurs at any street width." | **נוסח הבעלים (2026-10-01):** "In impulse, the height effect does not reverse at s̃ = 1 in most series (12 of 16 remain positive above it)." | 3b: ‏s̃<1 ‏8/8 חיוביים; ‏s̃>1 ‏12/16 חיוביים, חציון +2.00; שליליים: (det1,B15,s20,W50), (det2,B15,s20,W50), (det2,B30,s20,W50), (det1,B15,s20,W500) |
| 23 | 8 | "A single logarithmic correction in s̃ is added, since the radius peaks at an intermediate scaled street width:" | **נוסח הבעלים (2026-10-01):** "A single logarithmic correction in s̃ is added:" (החלק "since the radius peaks at an intermediate scaled street width" נמחק) | Table 2 החדשה: שיא ב־s̃ = exp(−r/(2r2)) = 3.6 (det1, בתוך התחום) ו־43.7 (det2, מחוץ ל־0.44–5.4: עולה מונוטונית). במקדמי ה־PDF: ‏1.4 ו־2.0 |
| 24 | 8 | "Fitting either form to the other quantity increases the prediction error by three to four percentage points, in both detonation scenarios." | "Fitting the impulse form to the peak overpressure raises the LOGO error from 9.4% to 11.5%, and fitting the peak-overpressure form to the impulse raises it from 7.1% to 12.8%." | scratchpad `logo_check/cross_logo_summary.csv` (LOGO צולב, pooled): +2.1 ו־+5.7 נק'; לפי det: P ‏+1.8/+2.5, I ‏+4.9/+6.6. אין טבלה כזו ברשומה; חישוב scratch על קוד הרשומה |
| 25 | 8 | "A narrower range can be delimited, with ρ between 0.31 and 0.56, s̃ between 0.50 and 5.4 m/kg1/3 and H/s not exceeding 3. Within it every withheld prediction falls below 20% error, in both quantities." | אם הגבולות נקראים מילולית: המשפט נכון ואפשר להוסיף "(16 configurations; largest errors 15.2% and 13.2%)". אם הם מעוגלים: לא נכון. אז צריך לצמצם את הגבולות או להחליף את המשפט. | `logo_cv_req_soft3_relwls_quad.csv` + `convergence_table`: מילולית N=16 (ρ 0.36, 0.444), מקס' P 15.21 (config_29), I 13.20 (config_30). מעוגל (כולל ρ=0.309, 0.5625, ‏s̃=5.43): ‏N=38, ‏P 23.66 (≥20: 67, 70, 83), I 28.27 (64, 70). ‏`safe_domain_req_soft3.csv` לא נוצר מחדש ברשומה |
| 26 | 9 | "A power law describes the impulse, in which this reversal does not occur." | לפי נוסח הבעלים ב־22: "A power law describes the impulse, in which the height effect does not reverse at s̃ = 1 in most series." | כמו 22 |
| F | 7 | (קשור ל־#5) "In peak overpressure this bound follows from the 10 kPa floor of Equation (2)…" | **נוסח הבעלים לשורה F חסר; הצעה זמנית:** "The 10 kPa floor alone would place the radius about 40% farther at the median (64% at the 90th percentile; Z ≈ 14.2 against 9.9 m/kg^1/3); the radius is set by the difference clause, not by the floor." | **נמדד על `27211b3` (2026-10-01):** רדיוס Req שמעבר לו P עירוני < 10 kPa בכל 91 פלחי θ (רצפה בלבד, אותה סריקה K=3 מרחוק לקרוב, תאים NaN כמו בייצור) מול R_conv,P של הרשומה (soft β=3): היחס חציון 1.403, ‏p90 ‏1.642, טווח 1.19–2.05, ≥1 ב־96/96. מול R_P קשיח: 1.552 / 1.861. ‏Z של רדיוס הרצפה: חציון 14.17, ‏p90 ‏16.33 (‏Z_conv,P: ‏9.91 / 11.92). בדיקת שחזור: הסריקה הקשיחה באותו סקריפט משחזרת את R_P הקשיח (max\|Δ\| 1.4e-14). scratchpad `inflation/floor_only.py`, ‏`floor_only_detail.csv` |
| I | 5–6 | Fig.2 (חילוץ הרדיוס, config_05) ו־Fig.3 (שדות יחס, config_05 ו־config_14) | Fig.2: לחדש (שינוי קטן). Fig.3: לחדש את פאנלים (c, d). | **Fig.2:** ‏`fig_scripts/fig_radius_extraction.py`, נוצרה 2026-09-27 23:26 עם קוד שלפני D34. נתוני config_05 לא השתנו (grid 1 זהה בכל המאגרים), אבל המיזוג של D34 משנה את השדה ואת הרדיוס: ‏R_conv,P ‏83.36 (‏`6b1a70b`) → 83.68 מ' (‏`27211b3`). **Fig.3:** ‏`make_fig2_ratiofields.py` (קורא `peakP1/impulse1/refP1/refI1` גולמיים מ־`data/raw_npz`, בלי קריטריון ובלי מיזוג), נוצרה 2026-09-27 23:17. ‏config_05 (‏a, b): המערכים זהים למאגר הנוכחי, אין שינוי. ‏config_14 (‏c, d): ‏grid 1 יוצא מחדש (A2, החתך העדין המוגבה ב־y=2.475 מ', ‏D32), ‏`peakP1` ו־`impulse1` שונים (max\|Δ\| 2.9e6 / 9.5e5 מול `raw_npz_2026-09-28`), ולכן הפאנלים ב־PDF הם של החתך המוגבה |

סך הכל: **30 שורות** (18 קבוצות ה־trace, ש־#14 מפוצלת בהן ל־4 ו־#16 ל־2, ועוד 8 חדשות).

## משפטים נתמכים (ללא שינוי)

- "The design comprises a balanced core block of 72 configurations ... (2 × 2 × 3 × 3 × 2 = 72)" וה־24 של ההרחבה: תצורות 1–72 הן המכפלה המלאה.
- Table 1 (ערכים וטווחי ρ, s̃, H/s), Eq.(1), Eq.(2), Eq.(4)–(8) כצורות.
- "The street width ranks first or second in both peak overpressure and impulse.": נכון בשתי השיטות (3a).
- "Over the 96 configurations, the two effects nearly cancel. ... It is an amplification, and it is present in almost every configuration.": ‏Λ_P חציון 1.01; ‏Λ_I>1 ב־91/96.
- "For s̃ > 1 m/kg1/3, amplification ceases to be systematic, and where it persists, it is weak.": ‏25/60 תצורות, חציון 0.976.
- "below it, taller buildings increase the radius, and above it they reduce it in nearly every case" (לחץ): ‏8/8 ו־14/16.
- "A denser layout returns more reflection and gives a larger radius.": ‏β_ρ>0 בשני ה־det.
- "In peak overpressure, the interactions between the inputs ... are as large as the effects of each input alone, and no smooth power law describes the radius.": ‏38.6% מול 36.1%; ‏R² של חוק חזקה 0.30/0.27 (מול 0.83/0.82 באימפולס). ב־trace סומן "cannot verify"; עכשיו נבדק.
- "The impulse falls consistently some 10% below the empirical curves": ‏−9.9% (Z 2–8), ‏−11.6%, ‏−12.4% (סעיף 4); "some 10–12%" מדויק יותר.
- "The mean absolute percentage error (MAPE) of the predicted radius remains below 10% in both quantities." (וכן בסיכום): ‏9.37 / 7.11. הערה: ‏det2 בלחץ 10.53.
- "The value a, at which the C2 term reverses, was fixed in advance and not fitted.": ‏`a_thresh` 1, 2.
- "A prediction should accordingly be sought only at a radius exceeding roughly 1.5 unit cells": תנאי מתועד (ALGORITHM).
- "The floor of Equation (2) and the impulse criterion of Equation (3) were kept as a sharp transition.": תואם D27.
- "This ratio depends on the tolerances adopted and is not a physical constant." ו־"The coefficients are specific to the tolerances of Equations (2) and (3).": נכונים, ומקבלים משקל נוסף אחרי D35.

</div>
