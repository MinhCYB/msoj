"""Polygon testlib validators for the authored beginner problem set."""
from .schema import ProblemSpec


def validator_source(problem: ProblemSpec) -> str:
    code = problem["code"]
    lines = [
        "#include <bits/stdc++.h>",
        '#include "testlib.h"',
        "using namespace std;",
        "int main(int argc, char* argv[]) {",
        "    registerValidation(argc, argv);",
        "    int n, m, q;",
    ]

    def read_value(lo, hi, name="value", indent="    "):
        lines.append(f'{indent}inf.readLong({lo}LL, {hi}LL, "{name}");')

    def read_line(count, lo, hi):
        if isinstance(count, str):
            lines.extend([
                f"    for (int i = 0; i < {count}; ++i) {{",
                f'        inf.readLong({lo}LL, {hi}LL, "value");',
                f"        if (i + 1 < {count}) inf.readSpace();",
                "    }",
            ])
        else:
            for i in range(count):
                read_value(lo, hi)
                if i + 1 < count:
                    lines.append("    inf.readSpace();")
        lines.append("    inf.readEoln();")

    basic = {
        "msb_expression": (-10**9, 10**9, 3),
        "msb_time": (0, 10**9, 1),
        "msb_compare": (-10**9, 10**9, 2),
        "msb_leapyear": (1, 9999, 1),
        "msb_ticket": (0, 120, 1),
        "msb_sum": (0, 10**6, 1),
        "msb_factorial": (0, 20, 1),
        "msb_rectangle": (1, 10**9, 2),
        "msb_trianglecheck": (1, 10**9, 3),
        "msb_grade": (0, 100, 1),
        "msb_sumodd": (0, 10**6, 1),
        "msb_divisorsum": (1, 10**6, 1),
    }
    if code in basic:
        lo, hi, count = basic[code]
        read_line(count, lo, hi)
    elif code == "msb_purchase":
        lines.extend(['    long long count = inf.readLong(0LL, 1000000LL, "n");', '    inf.readSpace();',
                      '    long long price = inf.readLong(1LL, 1000000LL, "p");', '    inf.readSpace();',
                      '    long long money = inf.readLong(0LL, 1000000000000LL, "money");',
                      '    ensuref(money >= count * price, "money must cover the purchase");', '    inf.readEoln();'])
    elif code == "msb_power":
        read_value(-10, 10, "a")
        lines.append("    inf.readSpace();")
        read_value(0, 18, "n")
        lines.append("    inf.readEoln();")
    elif code == "msb_divmod":
        read_value(0, 10**12, "n")
        lines.append("    inf.readSpace();")
        read_value(1, 10**6, "k")
        lines.append("    inf.readEoln();")
    elif code == "msb_countmultiples":
        lines.extend(['    n = inf.readInt(1, 10000, "n");', "    inf.readSpace();",
                      '    inf.readInt(1, 1000, "k");', "    inf.readEoln();"])
        read_line("n", -10**6, 10**6)
    elif code in {"msb_digitcount", "msb_digitsum", "msb_digitmax", "msb_reverseint", "msb_palint"}:
        read_value(0, 10**18)
        lines.append("    inf.readEoln();")
    elif code in {"msb_arraysum", "msb_arraycount", "msb_minpos", "msb_reversearray"}:
        lines.extend(['    n = inf.readInt(1, 100000, "n");', "    inf.readEoln();"])
        read_line("n", -10**9, 10**9)
    elif code in {"msb_distinct", "msb_mode", "msb_missing", "msb_firstrepeat"}:
        lines.extend(['    n = inf.readInt(1, 100000, "n");', "    inf.readEoln();"])
        read_line("n", 0, 1000)
    elif code == "msb_arrayfind":
        lines.extend(['    n = inf.readInt(1, 100000, "n");', "    inf.readSpace();",
                      '    inf.readInt(-1000000000, 1000000000, "x");', "    inf.readEoln();"])
        read_line("n", -10**9, 10**9)
    elif code == "msb_freqquery":
        lines.extend(['    n = inf.readInt(1, 100000, "n");', "    inf.readEoln();"])
        read_line("n", 0, 1000)
        lines.extend(['    q = inf.readInt(1, 1000, "q");', "    inf.readEoln();"])
        read_line("q", 0, 1000)
    elif code in {"msb_reversestr", "msb_wordcount"}:
        lines.extend([
            '    string s = inf.readLine();',
            "    ensure(s.size() <= 100000);",
        ])
        if code == "msb_reversestr":
            lines.append("    for (unsigned char c : s) ensure(c >= 32 && c <= 126);")
        else:
            lines.append("    for (char c : s) ensure((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || c == ' ');")
    elif code in {"msb_charcount", "msb_caseconvert"}:
        lines.extend(['    string s = inf.readToken();',
                      '    ensure(s.size() >= 1 && s.size() <= 100000);'])
        if code == "msb_charcount":
            lines.extend(["    for (char c : s) ensure(c >= 'a' && c <= 'z');", '    inf.readEoln();',
                          '    string target = inf.readToken("[a-z]", "c");', '    inf.readEoln();'])
        else:
            lines.extend(["    for (char c : s) ensure((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z'));",
                          '    inf.readEoln();'])
    elif code == "msb_palinstr":
        lines.extend([
            '    string s = inf.readToken();',
            "    ensure(s.size() >= 1 && s.size() <= 100000);",
            "    for (char c : s) ensure(c >= 'a' && c <= 'z');",
            "    inf.readEoln();",
        ])
    elif code in {"msb_rowscols", "msb_border", "msb_matrixmax", "msb_rowmax"}:
        lines.extend(['    n = inf.readInt(1, 200, "n");', "    inf.readSpace();",
                      '    m = inf.readInt(1, 200, "m");', "    inf.readEoln();"])
        lines.extend([
            "    for (int i = 0; i < n; ++i) {",
            "        for (int j = 0; j < m; ++j) {",
            '            inf.readLong(-1000000000LL, 1000000000LL, "a");',
            "            if (j + 1 < m) inf.readSpace();",
            "        }",
            "        inf.readEoln();",
            "    }",
        ])
    elif code == "msb_diagonals":
        lines.extend(['    n = inf.readInt(1, 200, "n");', "    inf.readEoln();"])
        lines.extend([
            "    for (int i = 0; i < n; ++i) {",
            "        for (int j = 0; j < n; ++j) {",
            '            inf.readLong(-1000000000LL, 1000000000LL, "a");',
            "            if (j + 1 < n) inf.readSpace();",
            "        }",
            "        inf.readEoln();",
            "    }",
        ])
    elif code == "msb_divisors":
        read_value(1, 100000)
        lines.append("    inf.readEoln();")
    elif code == "msb_prime":
        read_value(0, 10**9)
        lines.append("    inf.readEoln();")
    elif code == "msb_gcdlcm":
        read_line(2, 1, 10**9)
    elif code == "msb_modsum":
        lines.extend(['    n = inf.readInt(1, 100000, "n");', "    inf.readSpace();",
                      '    inf.readLong(1, 1000000000LL, "m");', "    inf.readEoln();"])
        read_line("n", 0, 10**9)
    else:
        raise ValueError(f"Unknown beginner problem code: {code}")

    lines.extend(["    inf.readEof();", "}"])
    return "\n".join(lines) + "\n"
