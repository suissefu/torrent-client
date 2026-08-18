from bitfield import Bitfield
test_cases = [
    {
        "name": "全部沒有",
        "piece_count": 8,
        "data": bytes([0b00000000]),
        "expected_ones": [],
    },
    {
        "name": "全部擁有",
        "piece_count": 8,
        "data": bytes([0b11111111]),
        "expected_ones": [0, 1, 2, 3, 4, 5, 6, 7],
    },
    {
        "name": "混合狀態",
        "piece_count": 8,
        "data": bytes([0b10110010]),
        "expected_ones": [0, 2, 3, 6],
    },
    {
        "name": "跨 byte",
        "piece_count": 10,
        "data": bytes([
            0b11001010,
            0b01000000,
        ]),
        "expected_ones": [0, 1, 4, 6, 9],
    },
    {
        "name": "只有第二個 byte 第一位",
        "piece_count": 9,
        "data": bytes([
            0b00000000,
            0b10000000,
        ]),
        "expected_ones": [8],
    },
    {
        "name": "16 pieces 交替",
        "piece_count": 16,
        "data": bytes([
            0b10101010,
            0b01010101,
        ]),
        "expected_ones": [
            0, 2, 4, 6,
            9, 11, 13, 15,
        ],
    },
    {
        "name": "10 pieces 全部擁有",
        "piece_count": 10,
        "data": bytes([
            0b11111111,
            0b11000000,
        ]),
        "expected_ones": list(range(10)),
    },
]

for case in test_cases:
    bitfield = Bitfield(
        case["piece_count"],
    )
    bitfield[:] = case["data"]
    actual = bitfield.get_all(1)

    print(case["name"])
    print("expected:", case["expected_ones"])
    print("actual:  ", actual)

    assert actual == case["expected_ones"]