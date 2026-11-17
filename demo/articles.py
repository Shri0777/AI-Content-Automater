"""Canned articles for demo mode, three for each topic preset.

Every company, person and figure here is invented, and every link points at
example.com, a domain reserved for examples. Nothing here is real news.
Each text is long enough (over 280 characters) to pass the newsroom's
"enough text to write an accurate post" gate, like a real article would.
"""

DEMO_ARTICLES = {
    "job_hiring": [
        {
            "title": "Northwind Robotics plans to hire 120 engineers this quarter",
            "text": "Northwind Robotics, a fictional warehouse automation "
            "company, says it will hire 120 software and hardware engineers "
            "across two offices. Most roles are open to remote applicants. "
            "The company says the new staff will work on its next picking "
            "robot, and that interviews will start next month with a short "
            "take-home task instead of a whiteboard round.",
        },
        {
            "title": "Contoso Health opens a graduate programme for data analysts",
            "text": "Contoso Health is starting a twelve-month programme for "
            "40 graduate data analysts. Applicants need basic SQL and Python. "
            "Graduates will rotate through three teams, from hospital "
            "scheduling to patient surveys, and each gets a mentor. The "
            "fictional company says applications close at the end of the "
            "month and that no prior healthcare experience is needed.",
        },
        {
            "title": "Fabrikam Games is recruiting 35 artists for a new studio",
            "text": "Fabrikam Games is opening a studio focused on mobile "
            "titles and is hiring 35 artists and animators over six months. "
            "The studio will build two small puzzle games first. Fabrikam, "
            "an invented company, says it wants portfolios rather than "
            "degrees, and that junior artists will be paired with senior "
            "staff for their first three months.",
        },
    ],
    "layoffs": [
        {
            "title": "Tailspin Logistics cuts 8 percent of staff after slow year",
            "text": "Tailspin Logistics told employees it will reduce its "
            "workforce by about 8 percent. Affected staff get 12 weeks of pay. "
            "The fictional company blamed lower shipping volumes over the "
            "past year and said most cuts fall in its sales and planning "
            "teams. It also promised help with job searches and said no "
            "warehouse roles are affected.",
        },
        {
            "title": "Litware closes its hardware unit, affecting 300 roles",
            "text": "Litware will close its hardware unit by March. The "
            "company says it will try to move 300 affected people to new "
            "teams. Litware, an invented firm, says the unit's devices sold "
            "fewer units than planned and that it will focus on software. "
            "Staff who cannot be moved will receive severance and keep their "
            "health cover for six months.",
        },
        {
            "title": "Adventure Works pauses hiring and trims marketing team",
            "text": "Adventure Works has paused most hiring and reduced its "
            "marketing team by 25 people, citing lower ticket sales. The "
            "fictional travel company says the pause will last at least two "
            "quarters. Open engineering roles stay open, it says, while "
            "marketing work moves to a smaller team that will focus on its "
            "most popular routes.",
        },
    ],
    "linux_tips": [
        {
            "title": "Find the largest folders with du and sort",
            "text": "Run du -h --max-depth=1 | sort -h to list the folders in "
            "the current directory by size, smallest first. The -h option "
            "prints sizes such as 4.0K or 1.2G, and sort -h understands those "
            "units. Add sudo if some folders belong to other users, and "
            "change --max-depth to look deeper. This demo tip is canned text, "
            "not advice written by an AI.",
        },
        {
            "title": "Follow a log file as it grows with tail -f",
            "text": "tail -f app.log prints new lines as they are written to "
            "app.log. Press Ctrl+C to stop following the file. Use tail -F "
            "instead when a log is rotated, because it reopens the file when "
            "it is replaced. Combine it with grep, as in tail -f app.log | "
            "grep ERROR, to watch only the lines you care about. This demo "
            "tip is canned text.",
        },
        {
            "title": "Repeat your last command with sudo using sudo !!",
            "text": "If a command fails because it needs administrator rights, "
            "type sudo !! to run the same command again with sudo. The shell "
            "replaces !! with your previous command before running it. Check "
            "what the command does before repeating it with more power, "
            "because sudo can change system files. This demo tip is canned "
            "text, not advice written by an AI.",
        },
    ],
    "ai_news": [
        {
            "title": "Woodgrove Labs releases a small open model for summaries",
            "text": "Woodgrove Labs, a fictional research group, published a "
            "small language model tuned for summarising long documents. The "
            "group says it runs on a laptop and was trained only on "
            "licensed text. Its report compares the model with two larger "
            "ones on three summary tests and admits it makes more mistakes "
            "with numbers and dates.",
        },
        {
            "title": "Proseware adds on-device speech recognition to its app",
            "text": "Proseware's note-taking app can now turn speech into text "
            "without sending audio to a server, the company says. The "
            "invented company says the feature works offline in five "
            "languages and uses less battery than its cloud version. It "
            "plans to publish an accuracy comparison next month and to add "
            "more languages next year.",
        },
        {
            "title": "Lucerne University study tests AI tutors in maths classes",
            "text": "Researchers at the fictional Lucerne University compared "
            "two groups of students and report modest gains with AI tutors. "
            "Students who used the tutor for twenty minutes a day scored "
            "slightly higher after one term. The authors warn the study was "
            "small, ran in only two schools, and needs repeating before "
            "anyone draws firm conclusions.",
        },
    ],
}
