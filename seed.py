"""Create (or reset) a demo account with realistic placement-prep data.

    python seed.py                      # local
    docker compose exec web python seed.py   # on the server

Dates are relative to today, so re-run it any time to refresh them.
"""
import re
import sys
from datetime import timedelta

from app.auth import hash_password
from app.db import get_db, init_db
from app.main import REVIEW_GAP, insert, today

EMAIL = "dev.shah@prepledger.local"
PASSWORD = "DevShah@2026"
NAME = "Dev Shah"

# company, role, status, ctc, city, source, applied(-days), next(+days), next step, link, notes
APPLICATIONS = [
    ("Wipro", "Turbo", "offer", 6.5, "Pune", "Campus", -48, None, "",
     "https://careers.wipro.com", "Offer letter received. Joining date to be confirmed. Keep as a safety option."),
    ("Capgemini", "Analyst", "rejected", 4.25, "Mumbai", "Campus", -41, None, "",
     "", "Cleared aptitude and technical, rejected after HR. Asked about bond terms."),
    ("TCS", "Digital", "oa", 7.0, "Mumbai", "Campus", -10, 3, "Digital NQT, online assessment",
     "https://www.tcs.com/careers", "Cognitive section is timed. Practise number series and puzzles."),
    ("Infosys", "Specialist Programmer", "interview", 9.5, "Bengaluru", "Campus", -22, 2, "Technical interview",
     "https://www.infosys.com/careers", "Cleared the coding round (2 of 3). Expect DSA plus project questions. Revise DBMS joins."),
    ("Cognizant", "GenC Elevate", "applied", 5.4, "Chennai", "Campus", -6, 8, "Assessment link expected",
     "", ""),
    ("Zoho", "Member Technical Staff", "interview", 8.0, "Chennai", "Referral", -26, 5, "Round 3: programming and design",
     "https://www.zoho.com/careers", "Cleared two written rounds. Round 3 is language-agnostic problem solving, practise without autocomplete."),
    ("Accenture", "Advanced App Engineering", "applied", 6.5, "Pune", "Off-campus drive", -4, 10, "Cognitive and coding assessment",
     "https://www.accenture.com/in-en/careers", ""),
    ("Amazon", "SDE-1", "wishlist", 28.0, "Hyderabad", "Careers page", None, 12, "Application closes",
     "https://www.amazon.jobs", "Needs a strong DSA base. Aim to finish the graphs and DP lists before applying."),
    ("Flipkart", "SDE-1", "wishlist", 24.0, "Bengaluru", "LinkedIn", None, 20, "Referral request to seniors",
     "", "Ask Karan (2024 batch) for a referral."),
    ("Razorpay", "Backend Engineer", "applied", 14.0, "Bengaluru", "LinkedIn", -9, None, "",
     "https://razorpay.com/jobs", "Applied with the URL shortener project on the resume."),
    ("Freshworks", "Associate Engineer", "rejected", 11.0, "Chennai", "Careers page", -33, None, "",
     "", "Rejected after the machine coding round. Did not manage time well. Needs timed practice."),
    ("Persistent Systems", "Software Engineer", "oa", 6.0, "Pune", "Campus", -7, 4, "Online test, 90 minutes",
     "", "Aptitude plus two coding questions."),
]

# title, topic, difficulty, platform, confidence (0 = not solved yet), days ago solved, minutes, note
PROBLEMS = [
    ("Two Sum", "Arrays", "easy", "LeetCode", 5, 38, 12, "Hash map of value to index."),
    ("Best Time to Buy and Sell Stock", "Arrays", "easy", "LeetCode", 4, 36, 15, "Track the minimum so far."),
    ("Contains Duplicate", "Arrays", "easy", "LeetCode", 5, 35, 6, ""),
    ("Product of Array Except Self", "Arrays", "medium", "LeetCode", 3, 30, 35, "Prefix and suffix passes, no division."),
    ("3Sum", "Arrays", "medium", "LeetCode", 2, 6, 50, "Sort, then two pointers. Skip duplicates carefully."),
    ("Container With Most Water", "Arrays", "medium", "LeetCode", 4, 24, 22, ""),
    ("Trapping Rain Water", "Arrays", "hard", "LeetCode", 1, 5, 70, "Could not get the two-pointer idea alone."),
    ("Valid Anagram", "Strings", "easy", "LeetCode", 5, 33, 8, ""),
    ("Group Anagrams", "Strings", "medium", "LeetCode", 4, 29, 25, "Sorted string as the key."),
    ("Longest Substring Without Repeating Characters", "Strings", "medium", "LeetCode", 3, 21, 40, "Sliding window with a last-seen map."),
    ("Valid Parentheses", "Stacks", "easy", "LeetCode", 5, 31, 10, ""),
    ("Min Stack", "Stacks", "medium", "LeetCode", 4, 17, 28, "Store (value, min so far) pairs."),
    ("Merge Two Sorted Lists", "Linked List", "easy", "LeetCode", 5, 28, 14, ""),
    ("Reverse Linked List", "Linked List", "easy", "LeetCode", 4, 27, 12, "Iterative first, then recursive."),
    ("Linked List Cycle", "Linked List", "easy", "LeetCode", 5, 23, 9, "Floyd's slow and fast pointers."),
    ("Binary Search", "Sorting & Searching", "easy", "LeetCode", 5, 32, 8, ""),
    ("Search in Rotated Sorted Array", "Sorting & Searching", "medium", "LeetCode", 2, 4, 45, "Decide which half is sorted first."),
    ("Merge Intervals", "Sorting & Searching", "medium", "LeetCode", 3, 14, 30, ""),
    ("Maximum Depth of Binary Tree", "Trees", "easy", "LeetCode", 5, 20, 7, ""),
    ("Binary Tree Level Order Traversal", "Trees", "medium", "LeetCode", 4, 13, 25, "BFS with a queue, track level size."),
    ("Validate Binary Search Tree", "Trees", "medium", "LeetCode", 2, 5, 38, "Pass min and max bounds down, not just the parent."),
    ("Number of Islands", "Graphs", "medium", "LeetCode", 3, 9, 30, ""),
    ("Clone Graph", "Graphs", "medium", "LeetCode", 2, 3, 42, "Map old node to new node while traversing."),
    ("Course Schedule", "Graphs", "medium", "LeetCode", 3, 5, 36, "Topological sort, Kahn's algorithm."),
    ("Climbing Stairs", "Dynamic Programming", "easy", "LeetCode", 5, 19, 10, ""),
    ("House Robber", "Dynamic Programming", "medium", "LeetCode", 4, 12, 26, ""),
    ("Coin Change", "Dynamic Programming", "medium", "LeetCode", 1, 2, 55, "Bottom-up table. Forgot the impossible case."),
    ("Longest Increasing Subsequence", "Dynamic Programming", "medium", "LeetCode", 2, 3, 48, "O(n^2) first, then patience sorting."),
    ("Top K Frequent Elements", "Hashing", "medium", "LeetCode", 4, 8, 24, "Bucket sort on frequencies."),
    ("Kth Largest Element in an Array", "Sorting & Searching", "medium", "LeetCode", 3, 2, 30, "Min-heap of size k."),
    # still to do
    ("Word Break", "Dynamic Programming", "medium", "LeetCode", 0, 0, None, ""),
    ("Median of Two Sorted Arrays", "Sorting & Searching", "hard", "LeetCode", 0, 0, None, "Save for after binary search is solid."),
    ("Sliding Window Maximum", "Arrays", "hard", "LeetCode", 0, 0, None, ""),
]

# kind, title, score, max, days ago, note
MOCKS = [
    ("aptitude", "Quant sectional 1", 13, 25, 46, "Lost time on time-speed-distance."),
    ("aptitude", "Quant sectional 2", 15, 25, 39, ""),
    ("dsa", "Coding round mock 1", 90, 300, 34, "Solved one of three."),
    ("aptitude", "Logical reasoning set", 17, 25, 27, ""),
    ("dsa", "Coding round mock 2", 150, 300, 22, "Two of three, second was brute force."),
    ("technical", "DBMS and OS quiz", 14, 20, 16, "Weak on normalisation and deadlock conditions."),
    ("aptitude", "Quant sectional 3", 19, 25, 11, "Better pacing."),
    ("dsa", "Coding round mock 3", 210, 300, 8, "Both easy and medium solved in 70 minutes."),
    ("interview", "Mock technical with senior", 6, 10, 5, "Good on arrays, hesitated on explaining complexity."),
    ("hr", "Mock HR round", 7, 10, 2, "Tighten the 'tell me about yourself' answer."),
]


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def main():
    init_db()
    t = today()
    day = lambda n: (t + timedelta(days=n)).isoformat()
    with get_db() as db:
        row = db.execute("SELECT id FROM users WHERE email=?", (EMAIL,)).fetchone()
        if row:
            uid = row["id"]
            for table in ("applications", "problems", "mocks", "activity"):
                db.execute(f"DELETE FROM {table} WHERE user_id=?", (uid,))
            db.execute("UPDATE users SET name=?, password_hash=? WHERE id=?", (NAME, hash_password(PASSWORD), uid))
        else:
            uid = db.execute("INSERT INTO users(email,name,password_hash) VALUES(?,?,?)",
                             (EMAIL, NAME, hash_password(PASSWORD))).lastrowid

        for company, role, status, ctc, city, source, applied, nxt, step, link, notes in APPLICATIONS:
            insert(db, "applications", uid, dict(
                company=company, role=role, status=status, ctc_lpa=ctc, location=city, source=source,
                applied_on=day(applied) if applied is not None else None, next_date=day(nxt) if nxt else None,
                next_step=step, link=link, notes=notes))

        for title, topic, diff, platform, conf, ago, minutes, note in PROBLEMS:
            if conf == 0:
                insert(db, "problems", uid, dict(title=title, topic=topic, difficulty=diff, platform=platform,
                       url=f"https://leetcode.com/problems/{slug(title)}/", status="todo", notes=note))
                continue
            solved = t - timedelta(days=ago)
            gap = REVIEW_GAP[conf]
            d, reviews = solved, 0
            # simulate reviews done on schedule; shaky problems (conf <= 2) stay mostly unreviewed
            while d + timedelta(days=gap) <= t and reviews < (1 if conf <= 2 else 9):
                d += timedelta(days=gap)
                reviews += 1
            insert(db, "problems", uid, dict(
                title=title, topic=topic, difficulty=diff, platform=platform,
                url=f"https://leetcode.com/problems/{slug(title)}/", status="revisit" if conf <= 2 else "solved",
                confidence=conf, time_min=minutes, solved_on=solved.isoformat(),
                last_reviewed=d.isoformat() if reviews else None,
                next_review=(d + timedelta(days=gap)).isoformat(), review_count=reviews, notes=note))

        for kind, title, score, mx, ago, note in MOCKS:
            d = (t - timedelta(days=ago)).isoformat()
            insert(db, "mocks", uid, dict(kind=kind, title=title, score=score, max_score=mx, taken_on=d, notes=note))

        # activity map: a 9-day streak up to today, a gap, then scattered earlier days (day offset: items logged)
        pattern = {0: 2, 1: 1, 2: 3, 3: 2, 4: 1, 5: 2, 6: 3, 7: 1, 8: 2,
                   11: 1, 12: 2, 14: 1, 15: 3, 17: 2, 19: 1, 21: 2, 22: 1, 25: 3, 26: 1, 29: 2, 33: 1,
                   34: 2, 40: 1, 41: 1, 45: 2, 52: 1, 58: 2, 63: 1, 70: 2}
        rows = [(uid, day(-n), "solve") for n, c in pattern.items() for _ in range(c)]
        db.executemany("INSERT INTO activity(user_id, day, kind) VALUES(?,?,?)", rows)

    print(f"Seeded {NAME}: {len(APPLICATIONS)} applications, {len(PROBLEMS)} problems, {len(MOCKS)} mock scores")
    print(f"  email:    {EMAIL}\n  password: {PASSWORD}")


if __name__ == "__main__":
    sys.exit(main())
