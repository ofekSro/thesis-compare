<div dir="rtl">

# עקיבות: מאמר ISIEMS v3 <-> רשומת compare_v7

תאריך: 2026-10-01. הרשומה: commit `27211b3` (טבלאות הרשומה) + `7b8fb1a` (`outputs/check_results/validation_comparison_req_soft3.csv`). סיומת הייצור: `req_soft3`.
המאמר: `isiems_paper/ISIEMS Paper v3.pdf` (2026-09-30 11:06, ראשי). `ISIEMS Paper v3.docx` (2026-09-29) נבדק רק לטקסט: אין הבדל מספרי במספרים המרכזיים (0.995, 1.261, 9.0, 11.6, 21.5, 8.8%, 7.2%, 17%, 75%, 3–4 נק', Table 2); ב־docx נשארו שינויים במעקב (tracked changes) שלא נסגרו (למשל "9.08.99", "~approximately 17%"). `ISIEMS_Paper.txt` לא נקרא.
הכל נקרא בקריאה בלבד. הערכים של הרשומה נקראו מ־`git show 27211b3:<path>` ו־`git show 7b8fb1a:<path>`. סקריפטים וביניים: scratchpad `.../scratchpad/trace/` (לא בריפו).

## ממצא מרכזי אחד

כמעט כל המספרים בפרקי התוצאות והחיזוי של המאמר מתאימים בדיוק לרשומה של **commit `430d004` (2026-08-03)**, כלומר לפני D2, D24, D31, D34 ו־D35: חציון Z_conv ‏8.986/11.615, מקסימום P ‏12.73, מקסימום I ‏21.49, ‏2 תצורות מעל Z=16, חציון CV ‏8.79/7.15, ומקדמי Table 2 (‏9.063 ו־14.936 מופיעים אות באות ב־`430d004`). הרשומה הנוכחית (`27211b3`) שונה. כלומר ה־PDF מתאר רשומה שכבר אינה הרשומה.
בנוסף: Eq.(3) במאמר היא צורת **D22** (`|ΔI|/W^1/3 < 20`, בלי רצועה יחסית ובלי רצפה), לא D24 ולא D35.

## תקציר: ספירה לפי סטטוס (68 שורות)

| סטטוס | מספר שורות | שורות |
|---|---|---|
| match | 30 | 1-9, 13-15, 19-22, 24, 26, 36, 37, 42-44, 49, 50, 55, 57, 64, 66, 67 |
| mismatch | 24 | 12, 16-18, 23, 25, 29-35, 38, 45, 47, 51-54, 58-61 |
| orphan (אין ברשומה) | 2 | 10, 11 |
| cannot verify | 10 | 27, 28, 39-41, 46, 48, 62, 65, 68 |
| see computation agent | 2 | 56, 63 |
| pending D36 | 0 | אף מספר במאמר לא תלוי בקובצי הרחוב (`street_anchors.csv`, `master_curve_g.csv`, `e_profile_validation_88.csv`); המאמר לא מזכיר את מודל הרחוב |

Mismatches בשורה אחת: Eq.(3) (D35); חציון Z_conv,P ‏9.0 מול 9.91; חציון Z_conv,I ‏11.6 מול 16.23; יחס ‏1.3 מול 1.64; מקסימום P ‏13 מול 14.70; "I>16 בשתיים" מול 51; מקסימום I ‏21.5 מול 29.21; Λ ‏0.995/1.261 מול 1.012/1.284; "17% ניפוח" מול +10.05%; כל Table 2 (4 שורות); Fig.4(a-f) ישן; Fig.5 (כל ה־inset); CV‏ 8.8/7.2% מול 9.60/6.84%; "משקל המטען ראשון ב־P"; "ρ עיקרי ב־I"; "אין רצפה באימפולס"; "10 kPa FF ב־Z נמוך מעט יותר"; הסכמה עם KB.

## בדיקת ניסוח הקריטריונים (D34, D35)

| נושא | מה כתוב במאמר | מה בתוקף | בעיה |
|---|---|---|---|
| Eq.(2) לחץ | `|P-Pff| < 10 kPa or P < 10 kPa` | `PARAMS['minPressure_kPa']=10` (קשיח: `<`/`<=` זניח), רך β=3, `softCap_kPa=20` | תקין, לא השתנה. תיאור הריכוך (חצי ב־10, אחד ב־20 kPa) תואם לקוד |
| Eq.(3) אימפולס | `|i-iff|/W^1/3 < 20 kPa·ms/kg^1/3` | `IMPULSE_CRITERION`: `|I/I_ff-1| <= 10%` **או** `I/W^1/3 < 23.6 kPa·ms/kg^1/3` (D35) | **שגוי.** זו צורת D22 (רצועה מקונ"מת מוחלטת 20). לא רצועה יחסית, לא רצפה, 20 במקום 23.6. גם לא D24 (`P_urban<10 kPa`) |
| "impulse tolerance ... smallest for which a radius was obtained in every configuration" | נימוק לבחירת 20 | D35: הרצפה 23.6 נגזרת מהאימפולס המקונ"מ ב־FF ב־Z שבו P=10 kPa (Z≈11.6), ממוצע על 5 משקלים; הרצועה 10% = פעמיים סובלנות רשת של 5% | הנימוק אינו הנימוק של D35 |
| "In peak overpressure, a second clause was added: a floor" / "No such floor applies in impulse" | הרצפה רק בלחץ | D35: יש רצפה גם באימפולס (על האימפולס המקונ"מ) | **סותר** |
| יחידות | kPa·ms/kg^1/3 | 23.6 Pa·s/kg^1/3 | שקול (1 kPa·ms = 1 Pa·s). אין בעיית יחידות, רק ערך (20 מול 23.6) |
| ניסוח D24 (רצפת לחץ לאימפולס `P_urban<10 kPa`) | לא מופיע | - | אין שרידי D24 בטקסט |
| ניסוח D31/D34 (חיתוך/מיזוג רשתות) | לא מופיע; כתוב רק "first street excluded" ו"three successive grids" | D34: מיזוג, מסכת בניינים בלבד, קריטריונים על שדות ממולאים | אין ניסוח ישן. המאמר גם לא מתאר את המיזוג (עוגן 5 של D34 משפיע בשפת התיבה העדינה, r≈100–141 מ'), אך זה השמטה ולא סתירה |
| "The coefficients are specific to the tolerances of Eq. (2) and (3)" | | | נכון, אך Table 2 היא של סובלנות אחרת (שורה 51-54) |

## טבלת הטענות

עמודות: מיקום במאמר; הטענה; מקור ברשומה (קובץ, עמודה, מסנן); ערך ברשומה; סטטוס. Z_conv = `RadiusP/W^(1/3)` (או `RadiusI`) מ־`outputs/tables/convergence_table_req_soft3.csv`, ‏W=`ChargeWeight`. מבחנים רלוונטיים: `tests/test_npz_anchors.py`, `tests/test_impulse_criterion.py`, `tests/test_grids_merge.py`; אין מבחן שננעל על חציוני Z_conv או על Table 2.

| # | מיקום | טענה | מקור ברשומה | ערך ברשומה | סטטוס |
|---|---|---|---|---|---|
| 1 | Methodology, p.3; Results p.6; Summary p.9 | 96 תצורות | `convergence_table_req_soft3.csv` | 96 שורות | match |
| 2 | p.4 | 72 ליבה (2·2·3·3·2) + 24 הרחבה (6·2·2); 18 גיאומטריות (12+6) | אותו קובץ, פירוק לפי config 1-72 / 73-96 | 72 / 24; 12 / 6 גיאומטריות (B,s,H) | match |
| 3 | Table 1 | ערכי W,B,s,H וחלוקה ליבה/הרחבה | `ChargeWeight, BuildingSize, StreetWidth, Height` | W {50,250,500,1000,1500}; B {10,15,30}; s {5,8,12,20}; H {4,10,12,15,24}. ליבה: W 50/500/1500, B 15/30, s 5/20, H 4/12/24; הרחבה: W 250/1000, B 10, s 5/8/12, H 10/15/24 | match |
| 4 | Table 1 | ρ ‏0.184-0.735 | `AreaDensity` | 0.1837-0.7347 | match |
| 5 | Table 1 | s̃ ‏0.44-5.4 | `StreetWidth/W^(1/3)` | 0.4368-5.4288 | match |
| 6 | Table 1 | H/s ‏0.20-4.8 | `Height/StreetWidth` | 0.20-4.80 | match |
| 7 | Eq.(1) | ρ=B²/(B+s)², s̃=s/W^1/3, H/s | `AreaDensity` (0.5625 ל־B15,s5) | תואם | match |
| 8 | Fig.4 | תוויות s̃ ‏1.36/5.43, 0.63/2.52, 0.44/1.75 | חישוב מ־s ו־W | 1.357/5.429, 0.630/2.520, 0.437/1.747 | match |
| 9 | Fig.1 | הצפוף ביותר והדליל ביותר | `AreaDensity` | צפוף 0.735 (B30,s5), דליל 0.184 (B15,s20): תואם לטבלה (הציור לא נבדק מול הרשומה) | match |
| 10 | Numerical approach, p.3 | 3 שלבי remap (1D, 2D ציר-סימטרי ל־s=5,8, 3D), רשת אחרונה עד 500 מ'; תאים 15/50/100 ס"מ | אין בטבלאות הרשומה (שלב 1 של הפרויקט, מחוץ ל־compare_v7) | - | orphan |
| 11 | p.3 | התכנסות רשת: 10% בלחץ ו־5% באימפולס ב־95.4-100% מ־632 נקודות | חיפוש `632` ב־docs/blastlib/tools/check_results: אין. ‏5% מוזכר רק כהסבר לרצועה 10% ב־`constants.py` | - | orphan |
| 12 | p.3 | הפותר מסכים עם KB עד כ־10% בלחץ שיא | `outputs/check_results/cfd_vs_kb_ufc_note.md` (PHY-06, מ־27.9, לא בקובצי 27211b3 שהשתנו) | CFD/KB לחץ: 0.91-0.93 ב־Z=2-8, 0.86 ב־10, 0.82 ב־12, 0.74 ב־16, 0.70 ב־20 | mismatch (חלקי: עד Z≈8 בערך 7-9%, מעבר לכך 14-30%; ההפניה היא [18]) |
| 13 | p.3 | אימפולס כ־10% מתחת ל־KB | אותו קובץ | חציון CFD/KB אימפולס 0.884 (טווח 0.833-0.915) | match |
| 14 | p.4 | ב־Z קבוע הלחץ ב־reference כמעט אינווריאנטי ל־W; האימפולס רק בצורה I/W^1/3 | `data/free_field_data.csv` (מתועד ב־git) | CV של P בין 5 המשקלים 3-7%; CV של I/W^1/3 ‏0.2-1.6%; CV של I הגולמי ‏35% | match |
| 15 | Eq.(2) | `|P-Pff|<10 kPa or P<10 kPa` | `blastlib/constants.py` `PARAMS['minPressure_kPa']=10` | 10 | match |
| 16 | Eq.(3) | `|i-iff|/W^1/3 < 20 kPa·ms/kg^1/3` | `constants.py` `IMPULSE_CRITERION` (`rel_band=0.10`, `floor_scaled=23.6`); D35 | `|I/Iff-1|<=10%` או `I/W^1/3<23.6` | mismatch |
| 17 | p.4 | "Its value is the smallest for which a radius was obtained in every configuration" | D35 / `constants.py` | הרצפה 23.6 מ־FF ב־P=10 kPa; הנימוק של 20 שייך ל־D22 | mismatch |
| 18 | p.4, p.7 | הרצפה רק בלחץ; "No such floor applies in impulse" | D35 | רצפה באימפולס קיימת: `I/W^1/3<23.6` | mismatch |
| 19 | p.5 | רצפת 10 kPa מעוגנת ב־IATG 02.20 | הערות `constants.py` (טבלה 8: מדרגות 9 ו־11 kPa) | תואם | match |
| 20 | p.5 | תאי "הרחוב הראשון" מוחרגים | `max_radius_per_Z_req_soft3.csv`, עמודה `ExcludeR` (7.906 מ' ל־config_01); ALGORITHM שורה ~557 | קיים | match |
| 21 | p.5, Eq.(4) | 91 קווים, סריקה מבחוץ, עצירה אחרי 3 תאים רצופים, איסוף לרדיוס רבע־עיגול שווה־שטח | `blastlib/constants.py` (`req`, K=3), ALGORITHM שורה ~117; `theta_radius_*_req_soft3.csv` (91 שורות θ) | תואם | match |
| 22 | p.5 | ריכוך: הסתברות חצי ב־10 kPa ואחד ב־20 kPa; רצפת Eq.2 ואימפולס נשארים חדים | `PARAMS['softBeta']=3`, `softCap_kPa=20`; D27 (אימפולס קשיח) | תואם | match |
| 23 | p.5-6 | הקריטריון המרוכך נותן רדיוס "approximately 17% larger at the median, ... on the safe side" | D4 (מדידה על `53b280c`, לא ב־27211b3): ניפוח β=3 מול קשיח | חציון +10.05%, p90 +19.34%, מקסימום +66.84%, **מינימום -13.25%**; ‏+17.3% היה ערך אוגוסט (`430d004`). D4 מציין שהטענה "~17%, תמיד שמרני" תוקנה. לא נמדד על הרשומה הנוכחית | mismatch |
| 24 | Eq.(5), (6) | Λ=Z_urban/Z_ff, ξ=Z_ff/Z_conv; Z_urban=R_urban/W^1/3 | `max_radius_per_Z_req_soft3.csv` (`Z`, `MaxR_P`, `MaxR_I`, `R_free`, `beyond_*`) | `R_free=Z·W^1/3`; Λ=`MaxR/R_free` מחושב. ξ אין עמודה, נגזר מ־`Z` ו־`RadiusP/I` | match (הגדרות) |
| 25 | p.6 | חציון Λ ‏0.995 בלחץ מול 1.261 באימפולס | אותו קובץ | שורות עם `beyond=False`: ‏1.012 / 1.284; כל השורות: 1.066 / 1.287; חציון-חציונים לפי תצורה: 1.036-1.073 / 1.273-1.279. גם על `430d004` יוצא 1.011/1.254 (בתוקף), כלומר ההגדרה המדויקת אינה ידועה | mismatch (סטייה 0.017-0.07 בלחץ, 0.02-0.03 באימפולס; הגדרת החציון לא מתועדת) |
| 26 | p.6 | בלחץ האפקטים כמעט מתקזזים; האימפולס מוגבר כמעט בכל תצורה | אותו קובץ, חציון Λ לפי תצורה | Λ_I>1 ב־95/96 (כל השורות) או 92/96 (תקפות); Λ_P>1 ב־71/96 או 58/96 | match (איכותי) |
| 27 | Fig.3, p.6 | שדות היחס P/Pff ו־i/iff בקרקע, רחוב צר ורחב, עד 80 מ' | שדות ב־`data/raw_npz` (לא בטבלאות); מקור: `make_fig3_16x9_v2.m` (09-29), `PS_Fig3.png` (10-01 09:10) | לא ניתן להשוות מספרית. `raw_npz` נבנה מחדש ב־10-01 (D34, 30-36/62) | cannot verify |
| 28 | Fig.2, p.5 | דוגמה לתצורה אחת: ‏R_conv חלק ≈85 מ' מול קשיח ≈78 מ'; רדיוסים לפי זווית | `theta_radius_P_req_soft3.csv` (רק הסיומת המרוככת); התצורה לא נקובה במאמר | אין קובץ קשיח ברשומה להשוואה; התצורה לא מזוהה | cannot verify |
| 29 | p.7 | חציון Z_conv,P ‏9.0 | `convergence_table_req_soft3.csv`, `RadiusP/W^1/3`, כל 96 | **9.907** (det1 9.40, det2 10.29) | mismatch |
| 30 | p.7 | חציון Z_conv,I ‏11.6 | `RadiusI/W^1/3` | **16.226** (D35 צוטט 16.19 בסקראץ'; הרשומה 16.23) | mismatch |
| 31 | p.7 | יחס "about 1.3" (11.6/9.0) | חישוב | 1.64 (יחס חציונים), 1.65 (חציון יחסים) | mismatch |
| 32 | p.7 | Z_conv,P לא עולה על 13 | `RadiusP/W^1/3` | מקסימום **14.695** (config_58); 3 תצורות מעל 13; 42 מעל 10 | mismatch |
| 33 | p.7 | Z_conv,I>16 ב"שתיים בלבד" | `RadiusI/W^1/3` | **51** תצורות מעל 16; 8 מעל 20 (22, 25, 26, 40, 43, 58, 61, 62) | mismatch |
| 34 | p.7 | ערך מקסימלי של Z_conv,I ‏21.5 | אותו | **29.210** (config_25) | mismatch |
| 35 | p.7 | "In peak overpressure this bound follows from the 10 kPa floor of Eq.(2), which the free-field overpressure reaches at a slightly smaller scaled distance" | `data/free_field_data.csv`: P=10 kPa ב־Z≈11.6 (D35); Z_conv,P מקסימום 14.70 | הרדיוס חורג מנקודת 10 kPa של ה־FF ב־3 יחידות; הטענה שהחסם נובע מהרצפה אינה מחזיקה כפי שנוסחה | mismatch |
| 36 | p.7 | רדיוס האימפולס גדול מזה של הלחץ | Z_conv,I>Z_conv,P | ב־96/96 (מובנה בצורת הקריטריונים, D24 ביקורת 2: לא ראיה פיזיקלית) | match |
| 37 | p.7 | רוחב הרחוב ראשון או שני בדירוג, בשני הגדלים (ליבה) | חישוב מחוון: חלק השונות (SS) של log Z_conv בליבה, בלי אינטראקציות | I: s 0.37, H 0.17, W 0.15, B 0.10; P: B 0.14, s 0.13, W 0.04, H 0.01 | match (שיטת הדירוג של המאמר לא מתועדת; חישוב אינדיקטיבי) |
| 38 | p.7 | בלחץ "the charge weight was ranked first" (על הרדיוס המקונ"מ) | אותו חישוב | W רק 0.04 מהשונות ב־Z_conv,P (רביעי). ב־R במטרים W הוא 0.92, אך המאמר מדבר על הרדיוס המקונ"מ | mismatch (אינדיקטיבי; השיטה לא מתועדת) |
| 39 | p.7 | באימפולס W פועל בעיקר דרך אינטראקציה עם s דרך s̃ | אין ניתוח אינטראקציות ברשומה | - | cannot verify |
| 40 | p.7 | הסף s̃=1 "proposed in advance" | טענת תהליך. אין עוגן ב־DECISIONS | - | cannot verify |
| 41 | p.7 | ב־s̃<1 הלחץ הוגבר ב"roughly 75%" מהתצורות | `max_radius_per_Z_req_soft3.csv`, Λ_P>1; 36 תצורות עם s̃<1 | תלוי בהגדרה: חציון Λ_P>1 לפי תצורה 94% (כל השורות) / 89% (תקפות); חלק השורות 85% / 72% (תקפות) | cannot verify |
| 42 | p.7 | ב־s̃>1 ההגברה אינה שיטתית | אותו | חציון Λ_P>1 ב־62% (כל) / 43% (תקפות) מ־60 תצורות | match |
| 43 | p.7 | dZ_conv,P/d(H/s) מתהפך ב־s̃=1: מתחת גובה מגדיל, מעל מקטין "in nearly every case" | שיפוע ריבועים פחותים על 3 גבהים, 24 סדרות ליבה, `RadiusP/W^1/3` | s̃<1: 8/8 חיוביים; s̃>1: 14/16 שליליים | match |
| 44 | p.7 | באימפולס אין היפוך "at any street width" | אותו, `RadiusI` | s̃<1: 8/8 חיוביים; s̃>1: 12/16 חיוביים, **4/16 שליליים** (D35: "מחזיקה עכשיו") | match (עם הסתייגות: 4 סדרות שליליות ב־s̃>1) |
| 45 | Fig.4(a-f) | רדיוס R_conv (מ') מול H, 3 משקלים | `convergence_table_req_soft3.csv` | הציור מתאים לרשומה `430d004` (config_01: P 28.3, I 51.1), הרשומה הנוכחית: config_01 P **33.0**, I **60.2**; config_04 P 33.1 / I 72.3; config_07 P 29.5 / I 71.7. כל הפאנלים ישנים | mismatch |
| 46 | Fig.4(g,h) | dZ/d(H/s) ל־24 סדרות | חישוב שלי (שורה 43-44) | איכותית תואם; ערכים נקודתיים לא נקראים מהציור. D35 צופה ששורה (h) תשתנה | cannot verify |
| 47 | p.7 | רדיוס האימפולס תלוי "mainly on ρ", כחוק חזקה חלק; צפוף => גדול | `final_production_convergence_coefficients_req_soft3.csv`: `p_rho`; חישוב: רגרסיית log Z_conv,I על log ρ, log s̃, log H/s | `p_rho`=0.274 (det1), 0.292 (det2), הגדול מבין המעריכים. מקדמים סטנדרטיים: det1 ρ 0.67 / s̃ 0.31 / H/s 0.56; det2 ρ 0.74 / **s̃ 0.75** / H/s 0.69 (D35: ‏s̃ 0.86 > ρ 0.77) | mismatch (חלקי: מחזיק ב־det1 ובאיחוד, נכשל/שוויון ב־det2) |
| 48 | p.7 | בלחץ האינטראקציות גדולות כמו האפקטים הבודדים; אין חוק חזקה חלק | אין ניתוח אינטראקציות ברשומה | - | cannot verify |
| 49 | Eq.(7) | `Z=s0[C0+C1(s̃/s0)+C2·ρ(s̃/s0-a)+C3·√ρ(H/s)(s0/s̃-1)]` | `blastlib/regression/convergence_models.py:17,79` | צורה זהה | match |
| 50 | Eq.(8) | `Z=s0·k·ρ^p(H/s)^q(s̃/s0)^r·exp(r2·ln²(s̃/s0))` | `convergence_models.py:204` ('quad') | צורה זהה | match |
| 51 | Table 2, Eq.7 det1 | C0,C1,C2,C3 = 9.063, -0.645, 2.018, 0.591 | `final_production_convergence_coefficients_req_soft3.csv`, `Det=1, Target=RadiusP` (`C0,C1_sW13,C2_switch,C3_canyon`) | 10.139, -0.762, 2.423, 0.418 | mismatch |
| 52 | Table 2, Eq.7 det2 | 11.858, -1.375, 2.782, 0.776 | `Det=2, RadiusP` | 11.605, -0.776, 1.926, 0.648 | mismatch |
| 53 | Table 2, Eq.8 det1 | k,p,q,r,r2 = 14.936, 0.203, 0.024, 0.065, -0.101 | `Det=1, RadiusI` (`A,p_rho,q_HoverS,r_sW13,r2_sW13sq`) | 20.486, 0.274, 0.112, 0.119, -0.046 | mismatch |
| 54 | Table 2, Eq.8 det2 | 14.602, 0.176, 0.079, 0.125, -0.089 | `Det=2, RadiusI` | 20.926, 0.292, 0.137, 0.209, -0.028 | mismatch |
| 55 | Table 2, עמודת a | a=1 (det1), a=2 (det2), קבוע מראש | `a_thresh` | 1.0, 2.0 | match |
| 56 | p.8 | "Fitting either form to the other quantity increases the prediction error by three to four percentage points" | אין טבלה ברשומה שמציגה התאמה צולבת (קיימים רק `logo_*_legacy_legacy`, `*_unified`, `*_soft2/4`) | - | see computation agent |
| 57 | p.8, Summary | MAPE של LOGO מתחת ל־10% בשני הגדלים | `logo_summary_req_soft3_relwls_quad.csv`, `Scope=pooled`, `Mean` | P 9.373, I 7.107 (P: det1 8.22, det2 10.53) | match (P ב־0.6 נק' מהגבול; det2 ב־P מעל 10) |
| 58 | Fig.5(a) | R²=0.941, MAPE 8.4%, חציון 5.7%, p90 18.7%, 62/96 בתוך ±10%, 89/96 ב־±20% | `logo_cv_req_soft3_relwls_quad.csv`, `Target=P` (R² על R במטרים) | R² 0.924; MAPE 9.37; חציון 6.72; p90 20.86; 59 ב־±10; 85 ב־±20; max 38.46 (config_58) | mismatch (הקובץ `PS_Fig4.png` מ־10-01 11:30 כבר מציג את ערכי הרשומה; ה־PDF לא) |
| 59 | Fig.5(b) | R²=0.926, MAPE 7.2%, חציון 5.9%, p90 16.4%, 68 ב־±10, 90 ב־±20 | `Target=I` | R² 0.951; MAPE 7.11; חציון 4.77; p90 17.91; 78 ב־±10; 86 ב־±20; max 31.13 (config_52) | mismatch (כנ"ל) |
| 60 | p.8 | 500 חלוקות אקראיות: חציון שגיאה 8.8% בלחץ | `cv_summary_req_soft3.csv`, חציון עמודה `conv_P` | 9.596 (ממוצע 9.665, p90 11.46) | mismatch (8.786 ב־`430d004`) |
| 61 | p.8 | אותו, 7.2% באימפולס | `conv_I` | 6.843 (ממוצע 6.901, p90 8.70) | mismatch (7.153 ב־`430d004`) |
| 62 | p.8 | "largest errors occur at the corners of the sampled ranges" | `logo_cv_req_soft3_relwls_quad.csv` | שגיאות הגדולות: P ב־58 (38.5), 87 (25.6), 62 (24.3), 70 (23.7); I ב־52 (31.1), 16 (29.8), 70 (28.3), 17 (26.7); בפינה 77-80: P 4.6/3.7/16.1/3.1, I 4.7/10.0/0.6/7.9. אין הגדרת "פינה" | cannot verify |
| 63 | p.8 | תחום צר: ρ 0.31-0.56, s̃ 0.50-5.4, H/s<=3; בתוכו כל תחזית נבדקת <20% | `logo_cv_req_soft3_relwls_quad.csv` + פרמטרים מ־`convergence_table`. `safe_domain_req_soft3.csv` הוא של `430d004` ולא נוצר מחדש | התחום (ρ גבולות מילוליים) = 16 תצורות (ρ 0.36 ו־0.444). שגיאה מקסימלית בתוכו: P **15.21%**, I **13.20%**; אין תצורה >=20%. (D35 בסקראץ': P 17.0, I 10.3.) אם מעגלים ρ=0.3086 ל־0.31, N=38 והשגיאה עולה ל־P 23.66 (67, 70, 83), I 28.27 (64, 70) | see computation agent (הטבלאות ישירות: תומכות בטענה לפי הגבולות המילוליים) |
| 64 | p.8 | נדרש R >= 1.5(B+s); "can be checked in advance" | ALGORITHM שורה ~678 (`Z_free·W^1/3 >~ 1.5(b+s)`) | ב־22 תצורות R_conv,P קטן מ־1.5(B+s) (מינימום 0.69), ב־9 תצורות R_conv,I (מינימום יחס 1.09); 3 מהן בתחום הצר ב־P (32, 35, 71) | match (תיעוד קיים; הטענה על תחום מותנית בתנאי זה) |
| 65 | p.9 | בלחץ ההגברה (Λ מול ξ) גדולה ליד המטען ודועכת; באימפולס אין תלות כזו, "single amplification factor" | `final_production_z_urban_coefficients_req_soft3.csv`: P `range_switch` (`A_switch`, `B_open`), I `canyon_trap` (`C1_amp,C2_self,C3_dilute`) | הצורות שונות; הטענה על מבנה תלות ב־Z_ff לא נבדקה | cannot verify |
| 66 | p.9 | משוואות סגורות ל־Z_urban הותאמו וממתינות ל־LOGO | אותו קובץ; `cv_summary` עמודות `z_P`,`z_I` | קיימות; חציון CV ‏8.76 / 7.60 (500 חלוקות) | match |
| 67 | Summary p.9 | 96 סימולציות; 3 פרמטרים; הלחץ משתנה מעט בממוצע והאימפולס מוגבר כמעט בכל תצורה; צורה אדיטיבית ללחץ וחוק חזקה לאימפולס; MAPE <10% | שורות 1, 24, 26, 49, 50, 57 | ראו שם | match |
| 68 | p.6 | הלחץ נקבע בעיקר מהחזית הראשונה; בחלק קטן מהמקומות השתקפות מאוחרת; בצרים השתקפויות מגבירות את החזית | אין טבלה ברשומה (שדות גולמיים בלבד) | - | cannot verify |

## משפטים שהרשומה ב־`27211b3` כבר אינה תומכת בהם (מילה במילה)

מקור הציטוטים: ה־PDF (שורות כתב הוצאה ללא סימני יחידות מורמות; `W1/3` = W^1/3).

מוגדרים כסותרים ישירות:

1. "The median scaled radius Zconv is 9.0 m/kg1/3 for peak overpressure and 11.6 m/kg1/3 for impulse." (רשומה: 9.907 ו־16.226)
2. "At the median, the impulse radius is therefore about 1.3 times the peak overpressure radius (11.6/9.0)." (רשומה: 1.64)
3. "Over all 96 configurations, the scaled radius in peak overpressure does not exceed 13 m/kg1/3." (רשומה: 14.695, config_58, 3 מעל 13)
4. "In impulse it exceeds 16 m/kg1/3 in two configurations only, and its largest value is 21.5 m/kg1/3." (רשומה: 51 מעל 16; מקסימום 29.210, config_25; D35 מציין שהטענה נכשלת)
5. "In peak overpressure this bound follows from the 10 kPa floor of Equation (2), which the free-field overpressure reaches at a slightly smaller scaled distance." (הרדיוס חורג מנקודת ה־10 kPa של ה־FF, Z≈11.6, עד 14.7)
6. "No such floor applies in impulse, and its radius extends farther." (D35: יש רצפת אימפולס. החלק "extends farther" נכון: 96/96)
7. Eq.(3): "|i-iff|/W^1/3 < 20 kPa·ms/kg^1/3" (בתוקף: `|I/Iff-1|<=10%` או `I/W^1/3<23.6`)
8. "The impulse tolerance was set on the scaled impulse. Its value is the smallest for which a radius was obtained in every configuration." (נימוק D22, אינו נימוק D35)
9. "In peak overpressure, a second clause was added: a floor below which the urban overpressure itself is too weak to matter structurally." (נכון ללחץ, אך בהקשר המשפט מרמז שלאימפולס אין סעיף כזה; ב־D35 יש)
10. "The smoothed criterion returns a radius that is approximately 17% larger at the median, which is on the safe side for protective design." (D4: חציון +10.05%, מינימום -13.25%; הטענה "תמיד שמרני" תוקנה)
11. "Expressed through the amplification factor of Equation (6), the median is 0.995 in peak overpressure against 1.261 in impulse." (רשומה: 1.012 / 1.284 בשורות תקפות; 1.066 / 1.287 בכל השורות)
12. "For peak overpressure, the charge weight was ranked first." (חישוב אינדיקטיבי על הרדיוס המקונ"מ: משקל המטען רביעי; שיטת הדירוג לא מתועדת)
13. "Among the three parameters of Equation (1), the impulse radius depends mainly on the plan-area density ρ, and the dependence is like a smooth power law." (נכשל ב־det2: s̃ ‏0.75 מול ρ 0.74 בחישוב שלי; D35: 0.86 מול 0.77. מחזיק ב־det1)
14. Table 2, כל 16 המקדמים הנומריים (השורות 51-54 למעלה), ולכן גם "Each row results from one fit to all configurations of its detonation scenario" כנאמר על הערכים המודפסים.
15. Fig.4 (a-f): כל ערכי R_conv בפאנלים (ישנים מ־`430d004`), ו־(g,h) צפוי להשתנות לפי D35.
16. Fig.5: "R² = 0.941, MAPE = 8.4 %, median error = 5.7 %, 90th percentile = 18.7 %, 62 of 96 within ±10 %, 89 of 96 within ±20 %" ו־"R² = 0.926, MAPE = 7.2 %, median error = 5.9 %, 90th percentile = 16.4 %, 68 of 96 within ±10 %, 90 of 96 within ±20 %" (רשומה: 0.924/9.4/6.7/20.9/59/85 ו־0.951/7.1/4.8/17.9/78/86)
17. "A supporting test, with 500 random splits of the configurations, returned median errors of 8.8% in peak overpressure and 7.2% in impulse." (רשומה: 9.60% ו־6.84%)
18. "The free-field predictions of the solver agree with Kingery and Bulmash to within approximately 10% in peak overpressure [18]." (רשומה, cfd_vs_kb: ‏7-9% רק עד Z≈8; 18% ב־Z=12, 26% ב־Z=16, 30% ב־Z=20)

נשארים נכונים או לא ניתנים להכרעה ולכן **לא** ברשימה: "MAPE ... below 10% in both quantities" (9.37 / 7.11), "radius exceeding roughly 1.5 unit cells", "every withheld prediction falls below 20% error" בתחום הצר (מקסימום 15.2% ו־13.2%), היפוך dZ/d(H/s) בלחץ, ו־"In impulse, no such reversal" (בהסתייגות 4/16).

טענות ש־D35 צפה שייכשלו, מול הרשומה: "ρ primary for Z_I" נכשל ב־det2 (שורה 47); "Z_I>16 only in two" נכשל (שורה 33; 51); Eq.(3) נכשל (שורה 16); Table 2 (שורות Eq.8) נכשל (53-54; וגם Eq.7, שורות 51-52, כי המאמר מ־`430d004`); Fig.4(g,h) לא ניתן להכרעה מספרית; Fig.5 נכשל (שורות 58-59). "אין היפוך" מחזיק (שורה 44).

## תוצאות הרשומה שהמאמר לא משתמש בהן

- `outputs/tables/best_convergence_coefficients_req_soft3.csv`, `best_z_urban_coefficients_req_soft3.csv`, `best_test_configs_req_soft3.csv` (20 תצורות מבחן, אין במאמר).
- `outputs/check_results/validation_comparison_req_soft3.csv` (`7b8fb1a`): 20 תצורות מבחן, שגיאה ממוצעת P ‏6.87%, I ‏4.09% (מקסימום 16.73 / 8.50). המאמר מצטט רק LOGO ו־500 חלוקות, לא את טבלת התיקוף הזו.
- `final_production_z_urban_coefficients_req_soft3.csv`: המקדמים של Z_urban לא מוצגים (המאמר אומר שהמשוואות "undergoing LOGO validation").
- `max_radius_per_Z_req_soft3.csv`: נשען עליו רק Λ במאמר (שורה 25); `beyond_P/I` לא מוזכרים.
- `theta_radius_P/I_req_soft3.csv` (דוגמת Fig.2 אפשרית); `logo_summary` לפי det (det1 P 8.22 / I 6.36; det2 P 10.53 / I 7.86).
- `outputs/check_results/safe_domain_req_soft3.csv` ו־`soft_beta_selection*.csv`: **לא נוצרו מחדש** ברשומה (נשארו של `430d004`/`53b280c`). המאמר מצטט את תחום הבטוח, ולכן המספרים שלו חייבים לבוא מחישוב מחדש (ראו שורה 63).
- קובצי הרחוב (`street_anchors.csv`, `master_curve_g.csv`, `e_profile_validation_88.csv`): ממתינים ל־D36; המאמר אינו משתמש בהם.

## איורים: סקריפט מקור וטריות

| איור | קובץ | מקור | תאריך | הערה |
|---|---|---|---|---|
| Fig.1 | `isiems_paper/images/2D_Geo_*`, `3D_Geo_*` | ללא סקריפט ברשומה | - | גיאומטריה בלבד, לא תלוי ברשומה |
| Fig.2 | `fig2_bare.png` | `make_fig2_ratiofields.py` (09-27), `fig_radius_extraction_v2.py` (09-27) | 09-27 23:17 | קורא שדות `raw_npz`; ישן מ־D34/D35 (10-01). **stale-figure** אפשרי; לא נבדק |
| Fig.3 | `PS_Fig3.png/pdf` | `make_fig3_16x9_v2.m` (09-29 14:15) | 10-01 09:10 | חדש מהסקריפט; תלוי ב־`raw_npz` שנבנה מחדש ב־10-01; לא ניתן לבדוק מול הרשומה |
| Fig.4 (השפעת גובה) | לא נמצא קובץ/סקריפט בתיקיית המאמר | - | - | הערכים תואמים ל־`430d004`. **stale-figure** |
| Fig.5 (LOGO) | `PS_Fig4.png/pdf` | `make_fig4.py` (09-28), קורא `outputs/check_results/logo_cv_req_soft3_relwls_quad.csv` מעץ העבודה | 10-01 11:30 | **הקובץ מעודכן ותואם לרשומה** (R² ‏0.924/0.951, MAPE 9.4/7.1, 59/85 ו־78/86). אבל ה־PDF של v3 (09-30 11:06) ישן ממנו ומכיל את הערכים הישנים. docstring של הסקריפט עדיין מתאר את רשומת 28.9 (D24) |

## הערות

- Λ, דירוג השפעות ושיפועי dZ/d(H/s) חושבו על ידי (scratchpad). שיטות המאמר לא מתועדות, ולכן אלה בדיקות אינדיקטיביות; סטטוס הוסק רק כשהתוצאה לא תלויה בהגדרה.
- מספרי D35 מהסקראץ' (LOGO I ממוצע 9.03%, תחום בטוח P 17.0 / I 10.3, 8 תצורות מעל Z=20) אינם זהים לרשומה ב־`27211b3` (LOGO I ממוצע 7.107; תחום בטוח P 15.2 / I 13.2; 8 תצורות מעל Z=20 זהות: 22, 25, 26, 40, 43, 58, 61, 62). מצוטט מהטבלאות בלבד.
- בטעות נוצרה בתיקיית OneDrive - Technion (מעל תיקיית `תואר שני`) שרשרת ריקה של תיקיות בשם `*` (`OneDrive - Technion\*\*\calculation_backup\compare_v7\docs\audit\2026-10-01`) כתוצאה מהרחבת glob בפקודת `mkdir`. אין בה קבצים. הפקודה למחיקתה נחסמה על ידי בדיקת בטיחות, והיא נשארה. יש למחוק ידנית (`rmdir` על התיקיות הריקות).

</div>
