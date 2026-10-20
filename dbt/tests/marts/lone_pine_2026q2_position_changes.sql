-- The cp4 done-criterion, checked against the source: the entries,
-- exits, increases and decreases of Lone Pine Capital, CIK 0001061165,
-- in 2026-06-30 against 2026-03-31. Expected rows come from its two
-- filings on sec.gov, fetched 2026-10-20, 0000919574-26-003439 (36
-- holdings) and 0000919574-26-005485 (34), read with include/edgar_xml.py
-- and compared in Python, not SQL: 13 entries, 15 exits, 8 increases and
-- 13 decreases, each row compared both ways in CUSIP, put or call, change
-- kind, the two amounts and the two values.
with expected as (
    select '02079K305' as cusip, cast(null as varchar) as put_call, 'increase' as change_kind, 215574 as shares_or_principal_amount, 187561 as previous_shares_or_principal_amount, 77039680 as value_usd, 53935041 as previous_value_usd
    union all select '032095101', cast(null as varchar), 'exit', cast(null as number), 223084, cast(null as number), 28186663
    union all select '038222105', cast(null as varchar), 'entry', 1207737, cast(null as number), 873193851, cast(null as number)
    union all select '03831W108', cast(null as varchar), 'decrease', 1042268, 1464923, 537007742, 583039354
    union all select '04010E109', cast(null as varchar), 'decrease', 368673, 393134, 294403824, 214120433
    union all select '09857L108', cast(null as varchar), 'exit', cast(null as number), 2405, cast(null as number), 10125820
    union all select '101137107', cast(null as varchar), 'exit', cast(null as number), 104655, cast(null as number), 6567101
    union all select '11271J107', cast(null as varchar), 'decrease', 792717, 11208969, 33761817, 453626975
    union all select '14040H105', cast(null as varchar), 'exit', cast(null as number), 2267056, cast(null as number), 413579026
    union all select '144285103', cast(null as varchar), 'decrease', 962839, 1817940, 593917609, 716541051
    union all select '146869102', cast(null as varchar), 'increase', 10520666, 1754709, 692470236, 551645415
    union all select '171779309', cast(null as varchar), 'exit', cast(null as number), 809522, cast(null as number), 314280726
    union all select '184496107', cast(null as varchar), 'exit', cast(null as number), 1754950, cast(null as number), 503196814
    union all select '219350105', cast(null as varchar), 'decrease', 2728058, 3718147, 696827855, 505556448
    union all select '29362U104', cast(null as varchar), 'exit', cast(null as number), 3115054, cast(null as number), 365208931
    union all select '43300A203', cast(null as varchar), 'exit', cast(null as number), 89249, cast(null as number), 27138836
    union all select '437076102', cast(null as varchar), 'entry', 2603189, cast(null as number), 918092697, cast(null as number)
    union all select '44812J104', cast(null as varchar), 'decrease', 5773045, 6078951, 666469180, 285163591
    union all select '45841N107', cast(null as varchar), 'entry', 577666, cast(null as number), 50280049, cast(null as number)
    union all select '48251W104', cast(null as varchar), 'exit', cast(null as number), 179308, cast(null as number), 16585990
    union all select '50012A108', cast(null as varchar), 'entry', 845070, cast(null as number), 63490109, cast(null as number)
    union all select '50212V100', cast(null as varchar), 'decrease', 1219099, 2049967, 343395806, 616691573
    union all select '576323109', cast(null as varchar), 'decrease', 1345157, 1531050, 559666021, 492600027
    union all select '57636Q104', cast(null as varchar), 'exit', cast(null as number), 57201, cast(null as number), 28581052
    union all select '58155Q103', cast(null as varchar), 'decrease', 57851, 392224, 43712216, 339414961
    union all select '58507V107', cast(null as varchar), 'increase', 20968367, 11789156, 826992394, 524617442
    union all select '71377A103', cast(null as varchar), 'increase', 5852740, 3978158, 654277805, 340769014
    union all select '778920306', cast(null as varchar), 'entry', 1209848, cast(null as number), 102425731, cast(null as number)
    union all select '81141R100', cast(null as varchar), 'entry', 494581, cast(null as number), 47395697, cast(null as number)
    union all select '859241101', cast(null as varchar), 'entry', 609643, cast(null as number), 511709948, cast(null as number)
    union all select '87305R109', cast(null as varchar), 'entry', 2738075, cast(null as number), 512074787, cast(null as number)
    union all select '874039100', cast(null as varchar), 'decrease', 101242, 1389530, 48350142, 469591664
    union all select '87422Q109', cast(null as varchar), 'exit', cast(null as number), 1817947, cast(null as number), 580343221
    union all select '88033G407', cast(null as varchar), 'exit', cast(null as number), 2258717, cast(null as number), 426242485
    union all select '880770102', cast(null as varchar), 'decrease', 1493080, 1872876, 722411827, 555232819
    union all select '88080T104', cast(null as varchar), 'increase', 24144625, 19921430, 596372238, 287466235
    union all select '893641100', cast(null as varchar), 'decrease', 28532, 35677, 38005765, 41348216
    union all select '912008109', cast(null as varchar), 'increase', 4914492, 3795998, 502506807, 350028976
    union all select '92826C839', cast(null as varchar), 'increase', 165960, 92775, 56939216, 28040316
    union all select '92840M102', cast(null as varchar), 'exit', cast(null as number), 6187585, cast(null as number), 930179653
    union all select '929160109', cast(null as varchar), 'exit', cast(null as number), 144179, cast(null as number), 39259942
    union all select 'G11448100', cast(null as varchar), 'entry', 7020026, cast(null as number), 111407813, cast(null as number)
    union all select 'G54950103', cast(null as varchar), 'entry', 1558081, cast(null as number), 808550554, cast(null as number)
    union all select 'G6683N103', cast(null as varchar), 'increase', 47219717, 38011225, 630855419, 546221303
    union all select 'G7997R103', cast(null as varchar), 'entry', 1000109, cast(null as number), 965105185, cast(null as number)
    union all select 'H5919C104', cast(null as varchar), 'entry', 13280030, cast(null as number), 470378663, cast(null as number)
    union all select 'L8681T102', cast(null as varchar), 'exit', cast(null as number), 68844, cast(null as number), 33383144
    union all select 'N07059210', cast(null as varchar), 'decrease', 569174, 655148, 1132337523, 865339133
    union all select 'N97284108', cast(null as varchar), 'entry', 4258008, cast(null as number), 1175934069, cast(null as number)
),

actual as (
    select
        cusip,
        put_call,
        change_kind,
        shares_or_principal_amount,
        previous_shares_or_principal_amount,
        value_usd,
        previous_value_usd
    from {{ ref('position_changes') }}
    where cik = '0001061165' and period_of_report = '2026-06-30'::date
)

(select 'missing' as side, * from expected minus select 'missing', * from actual)
union all
(select 'unexpected' as side, * from actual minus select 'unexpected', * from expected)
