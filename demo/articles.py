"""Canned articles for demo mode, three for each topic preset.

Every company, person and figure here is invented, and every link points at
example.com, a domain reserved for examples. Nothing here is real news.
"""

DEMO_ARTICLES = {
    "job_hiring": [
        {
            "title": "Northwind Robotics plans to hire 120 engineers this quarter",
            "text": "Northwind Robotics, a fictional warehouse automation "
            "company, says it will hire 120 software and hardware engineers "
            "across two offices. Most roles are open to remote applicants.",
        },
        {
            "title": "Contoso Health opens a graduate programme for data analysts",
            "text": "Contoso Health is starting a twelve-month programme for "
            "40 graduate data analysts. Applicants need basic SQL and Python.",
        },
        {
            "title": "Fabrikam Games is recruiting 35 artists for a new studio",
            "text": "Fabrikam Games is opening a studio focused on mobile "
            "titles and is hiring 35 artists and animators over six months.",
        },
    ],
    "layoffs": [
        {
            "title": "Tailspin Logistics cuts 8 percent of staff after slow year",
            "text": "Tailspin Logistics told employees it will reduce its "
            "workforce by about 8 percent. Affected staff get 12 weeks of pay.",
        },
        {
            "title": "Litware closes its hardware unit, affecting 300 roles",
            "text": "Litware will close its hardware unit by March. The "
            "company says it will try to move 300 affected people to new teams.",
        },
        {
            "title": "Adventure Works pauses hiring and trims marketing team",
            "text": "Adventure Works has paused most hiring and reduced its "
            "marketing team by 25 people, citing lower ticket sales.",
        },
    ],
    "linux_tips": [
        {
            "title": "Find the largest folders with du and sort",
            "text": "Run du -h --max-depth=1 | sort -h to list the folders in "
            "the current directory by size, smallest first.",
        },
        {
            "title": "Follow a log file as it grows with tail -f",
            "text": "tail -f app.log prints new lines as they are written to "
            "app.log. Press Ctrl+C to stop following the file.",
        },
        {
            "title": "Repeat your last command with sudo using sudo !!",
            "text": "If a command fails because it needs administrator rights, "
            "type sudo !! to run the same command again with sudo.",
        },
    ],
    "ai_news": [
        {
            "title": "Woodgrove Labs releases a small open model for summaries",
            "text": "Woodgrove Labs, a fictional research group, published a "
            "small language model tuned for summarising long documents.",
        },
        {
            "title": "Proseware adds on-device speech recognition to its app",
            "text": "Proseware's note-taking app can now turn speech into text "
            "without sending audio to a server, the company says.",
        },
        {
            "title": "Lucerne University study tests AI tutors in maths classes",
            "text": "Researchers at the fictional Lucerne University compared "
            "two groups of students and report modest gains with AI tutors.",
        },
    ],
}
