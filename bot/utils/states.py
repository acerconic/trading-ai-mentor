from aiogram.fsm.state import State, StatesGroup

class StudyState(StatesGroup):
    waiting_for_pdf = State()
    reading_pdf = State()

class PracticeState(StatesGroup):
    waiting_for_chart = State()
