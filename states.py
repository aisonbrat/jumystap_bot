from aiogram.fsm.state import State, StatesGroup


class AuthFlow(StatesGroup):
    """Waiting for the user to type the unlock password."""
    waiting_password = State()


class PostFlow(StatesGroup):
    """FSM states for the post creation / preview workflow."""
    reviewing = State()        # Preview visible, control panel active
    waiting_photo = State()    # Expecting an image from the admin
    editing_buttons = State()  # Expecting manual button override text


class SettingsFlow(StatesGroup):
    """FSM states for the /settings panel."""
    menu = State()
    edit_footer = State()
    edit_perm_text = State()
    edit_perm_url = State()
    edit_channel = State()
