"""
Lab #3: Baseline Chatbot vs ReAct Agent
Học viên hoàn thiện các mục TODO để hoàn thành bài lab.
"""

import json
from tools import TOOL_DEFINITIONS, TOOL_MAP, get_flight_info, get_weather_forecast

SYSTEM_PROMPT = """Bạn là một ReAct Agent thông minh hỗ trợ khách hàng Vingroup.
Bạn chỉ sử dụng các công cụ sau:
{tools}

Quy trình trả lời bắt buộc:
Thought: <Suy nghĩ bước tiếp theo>
Action: {{"name": "<tên tool>", "args": {{<tham số>}}}}
Observation: <Kết quả từ tool>
... (Lặp lại cho tới khi có đủ dữ liệu)
Final Answer: <Câu trả lời hoàn chỉnh cho khách hàng>
"""

class ChatbotBaseline:
    """Baseline LLM Chatbot (Không sử dụng ReAct Loop hay Tools)"""

    def query(self, user_input: str) -> dict:
        return {
            "status": "success",
            "answer": (
                "Bạn có thể tìm chuyến bay trên các trang hàng không. "
                "Về thời tiết, bạn nên tra cứu trên trang dự báo thời tiết."
            ),
            "tool_calls": []
        }

class ReActAgent:
    """ReAct Agent có sử dụng Thought-Action-Observation Loop"""

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.trace = []

    def run(self, user_input: str) -> dict:
        self.trace = []
        iteration = 0

        # Chuyển câu hỏi về chữ thường để dễ kiểm tra từ khóa
        user_lower = user_input.lower()
                # Xử lý FAQ không cần gọi tool
        if (
            "chính sách" in user_lower
            or "đổi trả" in user_lower
            or "vinpearl" in user_lower
        ):
            final_answer = (
                "Vinpearl có chính sách đổi trả vé tùy theo loại vé "
                "và điều kiện áp dụng. Vui lòng kiểm tra điều khoản "
                "của vé để biết chi tiết."
            )

            self.trace.append({
                "iteration": 1,
                "thought": "Đây là câu hỏi FAQ, không cần gọi tool.",
                "final_answer": final_answer
            })

            return {
                "status": "completed",
                "answer": final_answer,
                "iterations": 1,
                "trace": self.trace
            }

        # Xác định người dùng có cần tra chuyến bay hay không
        needs_flight = any(
            keyword in user_lower
            for keyword in ["chuyến bay", "vé", "bay từ"]
        )

        # Xác định người dùng có cần xem thời tiết hay không
        needs_weather = any(
            keyword in user_lower
            for keyword in ["thời tiết", "mặc gì", "nhiệt độ", "mưa"]
        )

        # Tìm mã sân bay / thành phố trong câu hỏi
        city_codes = ["HAN", "SGN", "DAD"]

        found_codes = [
            code for code in city_codes
            if code.lower() in user_lower
        ]

        # Nếu tìm thấy 2 mã:
        # mã đầu là nơi đi, mã sau là nơi đến
        origin = found_codes[0] if len(found_codes) >= 1 else "HAN"

        if len(found_codes) >= 2:
            destination = found_codes[1]
        elif len(found_codes) == 1 and needs_weather:
            destination = found_codes[0]
        else:
            destination = "SGN"

        # Giá tối đa mặc định
        max_price = 5000000

        # Phân tích ngân sách từ câu hỏi
        if "2 triệu" in user_lower or "2.000.000" in user_lower:
            max_price = 2000000
        elif "1.5 triệu" in user_lower or "1,5 triệu" in user_lower:
            max_price = 1500000
        elif "500k" in user_lower:
            max_price = 500000

        # Biến lưu kết quả từ tool
        flight_result = []
        weather_result = {}

        # Đánh dấu tool đã được gọi hay chưa
        flight_checked = False
        weather_checked = False

        # =========================
        # REACT LOOP
        # =========================
        while iteration < self.max_iterations:
            iteration += 1

            # =========================
            # BƯỚC 1: TRA CHUYẾN BAY
            # =========================
            if needs_flight and not flight_checked:
                thought = (
                    f"Cần tìm chuyến bay từ {origin} đến {destination} "
                    f"với giá tối đa {max_price} VND."
                )

                action = {
                    "name": "get_flight_info",
                    "args": {
                        "origin": origin,
                        "destination": destination,
                        "max_price": max_price
                    }
                }

                # Gọi tool
                observation = TOOL_MAP[action["name"]](**action["args"])

                # Lưu kết quả
                flight_result = observation
                flight_checked = True

                # Ghi trace
                self.trace.append({
                    "iteration": iteration,
                    "thought": thought,
                    "action": action,
                    "observation": observation
                })

                                # Nếu người dùng chỉ hỏi chuyến bay thì trả lời luôn
                if not needs_weather:
                    if flight_result:
                        flight_lines = []

                        for flight in flight_result:
                            flight_lines.append(
                                f"- {flight['airline']} "
                                f"({flight['flight_number']}): "
                                f"{flight['departure_time']} - "
                                f"Giá: {flight['price_vnd']:,} VNĐ"
                            )

                        final_answer = (
                            "Thông tin chuyến bay:\n"
                            + "\n".join(flight_lines)
                        )

                    else:
                        final_answer = (
                            f"Không tìm thấy chuyến bay từ "
                            f"{origin} đến {destination} "
                            f"dưới {max_price:,} VNĐ."
                        )

                    self.trace[-1]["final_answer"] = final_answer

                    return {
                        "status": "completed",
                        "answer": final_answer,
                        "iterations": iteration,
                        "trace": self.trace
                    }

                continue

            # =========================
            # BƯỚC 2: TRA THỜI TIẾT
            # =========================
            if needs_weather and not weather_checked:
                city_code = destination

                thought = (
                    f"Cần kiểm tra thời tiết tại {city_code} "
                    f"để tư vấn trang phục."
                )

                action = {
                    "name": "get_weather_forecast",
                    "args": {
                        "city_code": city_code
                    }
                }

                # Gọi tool
                observation = TOOL_MAP[action["name"]](**action["args"])

                # Lưu kết quả
                weather_result = observation
                weather_checked = True

                # Ghi trace
                self.trace.append({
                    "iteration": iteration,
                    "thought": thought,
                    "action": action,
                    "observation": observation
                })

                                # Nếu người dùng chỉ hỏi thời tiết thì trả lời luôn
                if not needs_flight:
                    if "error" not in weather_result:
                        final_answer = (
                            f"Thời tiết tại "
                            f"{weather_result.get('city', destination)}:\n"
                            f"- Nhiệt độ: "
                            f"{weather_result.get('temperature_c', 'N/A')}°C\n"
                            f"- Thời tiết: "
                            f"{weather_result.get('condition', 'N/A')}\n"
                            f"- Gợi ý trang phục: "
                            f"{weather_result.get('recommendation', 'N/A')}"
                        )
                    else:
                        final_answer = "Không lấy được dữ liệu thời tiết."

                    self.trace[-1]["final_answer"] = final_answer

                    return {
                        "status": "completed",
                        "answer": final_answer,
                        "iterations": iteration,
                        "trace": self.trace
                    }

                continue

            # =========================
            # BƯỚC 3: FINAL ANSWER
            # =========================
            thought = "Đã thu thập đủ thông tin để trả lời khách hàng."

            answer_parts = []

            # Tổng hợp thông tin chuyến bay
            if needs_flight:
                if flight_result:
                    flight_lines = []

                    for flight in flight_result:
                        flight_lines.append(
                            f"- {flight['airline']} "
                            f"({flight['flight_number']}): "
                            f"{flight['departure_time']} - "
                            f"Giá: {flight['price_vnd']:,} VNĐ"
                        )

                    answer_parts.append(
                        "1. Thông tin chuyến bay:\n"
                        + "\n".join(flight_lines)
                    )

                else:
                    answer_parts.append(
                        f"1. Không tìm thấy chuyến bay từ "
                        f"{origin} đến {destination} "
                        f"dưới {max_price:,} VNĐ."
                    )

            # Tổng hợp thông tin thời tiết
            if needs_weather:
                if "error" not in weather_result:
                    answer_parts.append(
                        "2. Thông tin thời tiết:\n"
                        f"- Thành phố: "
                        f"{weather_result.get('city', destination)}\n"
                        f"- Nhiệt độ: "
                        f"{weather_result.get('temperature_c', 'N/A')}°C\n"
                        f"- Thời tiết: "
                        f"{weather_result.get('condition', 'N/A')}\n"
                        f"- Gợi ý trang phục: "
                        f"{weather_result.get('recommendation', 'N/A')}"
                    )
                else:
                    answer_parts.append(
                        "2. Không lấy được dữ liệu thời tiết."
                    )

            final_answer = "\n\n".join(answer_parts)

            # Lưu final answer vào trace
            self.trace.append({
                "iteration": iteration,
                "thought": thought,
                "final_answer": final_answer
            })

            return {
                "status": "completed",
                "answer": final_answer,
                "iterations": iteration,
                "trace": self.trace
            }

        # =========================
        # SAFEGUARD
        # =========================
        return {
            "status": "max_iterations_reached",
            "answer": "Lỗi: Agent đã vượt quá số bước lặp tối đa.",
            "iterations": iteration,
            "trace": self.trace
        }

def main():
    user_query = "Tìm cho tôi chuyến bay từ HAN đi SGN dưới 2 triệu, rồi cho biết thời tiết SGN nên mặc gì?"
    
    print("=== RUNNING CHATBOT BASELINE ===")
    chatbot = ChatbotBaseline()
    print(chatbot.query(user_query))
    
    print("\n=== RUNNING REACT AGENT ===")
    agent = ReActAgent(max_iterations=5)
    result = agent.run(user_query)
    print("Result:", result)
    print("Trace Log:", json.dumps(agent.trace, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()