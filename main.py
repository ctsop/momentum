import os
os.environ['KIVY_AUDIO'] = 'sdl2'

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.properties import ObjectProperty, StringProperty, NumericProperty, ListProperty, DictProperty
from kivy.clock import Clock
from kivy.storage.jsonstore import JsonStore
from functools import partial
from kivy.core.audio import SoundLoader
from kivy.uix.popup import Popup
from kivy.uix.label import Label


# --- NEW: Popup classes that link to our .kv definitions ---
class EditPopup(Popup):
    task_data = DictProperty(None)
    task_index = NumericProperty(None)
    app_root = ObjectProperty(None)

    def save_changes(self):
        new_name = self.ids.task_name_input.text
        try:
            new_duration_mins = int(self.ids.task_duration_input.text)
        except ValueError:
            return # Or show an error

        if not new_name:
            return # Or show an error

        self.app_root.update_task(self.task_index, new_name, new_duration_mins)
        self.dismiss()

class DeletePopup(Popup):
    task_index = NumericProperty(None)
    app_root = ObjectProperty(None)

    def confirm_delete(self):
        self.app_root.delete_task(self.task_index)
        self.dismiss()


class MomentumLayout(BoxLayout):
    task_list = ObjectProperty(None)
    task_name_input = ObjectProperty(None)
    task_duration_input = ObjectProperty(None)
    
    timer_text = StringProperty("00:00:00")
    active_task_index = NumericProperty(-1)
    timer_event = None
    progress_fraction = NumericProperty(0)
    alert_sound = SoundLoader.load('alert.wav')
    tasks_data = ListProperty([])
    store = JsonStore('momentum_data.json')

    def add_task(self, *args):
        task_name = self.task_name_input.text
        try:
            duration_in_minutes = int(self.task_duration_input.text)
        except ValueError:
            return

        if not task_name:
            return
        
        duration_in_seconds = duration_in_minutes * 60
        self.tasks_data.append({
            'name': task_name,
            'duration': duration_in_seconds,
            'remaining': duration_in_seconds
        })
        
        self.rebuild_task_list_ui()
        self.select_task(len(self.tasks_data) - 1)
        self.task_name_input.text = ""
        self.task_duration_input.text = ""

    def select_task(self, index, *args):
        if self.active_task_index != -1 and self.active_task_index < len(self.tasks_data):
            self.tasks_data[self.active_task_index]['remaining'] = self.get_current_timer_remaining()
        
        self.pause_timer()
        self.active_task_index = index
        self.update_timer_display()
        self.rebuild_task_list_ui()

    def rebuild_task_list_ui(self, *args):
        self.task_list.clear_widgets()
        for i, task in enumerate(self.tasks_data):
            # --- MODIFIED: Each task is now a horizontal box with multiple widgets ---
            task_layout = BoxLayout(size_hint_y=None, height='40dp', spacing=5)

            # The main button that shows the task name and selects it
            task_button = Button(
                text=f"Task: {task['name']}  ({task['duration'] // 60} mins)"
            )
            task_button.bind(on_press=partial(self.select_task, i))
            if i == self.active_task_index:
                task_button.background_color = (0.2, 0.6, 0.8, 1)
            else:
                task_button.background_color = (0.5, 0.5, 0.5, 1)

            # Edit button
            edit_button = Button(
                text="Edit", 
                size_hint_x=0.2
            )
            edit_button.bind(on_press=partial(self.open_edit_popup, i))

            # Delete button
            delete_button = Button(
                text="Del",
                size_hint_x=0.15,
                background_color=(0.9, 0.3, 0.3, 1) # Red color
            )
            delete_button.bind(on_press=partial(self.open_delete_popup, i))

            task_layout.add_widget(task_button)
            task_layout.add_widget(edit_button)
            task_layout.add_widget(delete_button)
            self.task_list.add_widget(task_layout)
    
    # --- NEW: Methods to handle popups and data changes ---
    def open_edit_popup(self, index, *args):
        popup = EditPopup(task_data=self.tasks_data[index], task_index=index, app_root=self)
        popup.open()

    def open_delete_popup(self, index, *args):
        popup = DeletePopup(task_index=index, app_root=self)
        popup.open()

    def update_task(self, index, new_name, new_duration_mins):
        duration_secs = new_duration_mins * 60
        self.tasks_data[index]['name'] = new_name
        self.tasks_data[index]['duration'] = duration_secs
        # Reset remaining time to new duration
        self.tasks_data[index]['remaining'] = duration_secs
        self.rebuild_task_list_ui()
        # If we edited the active task, update the main timer
        if index == self.active_task_index:
            self.update_timer_display()

    def delete_task(self, index):
        # If we delete the currently active task, reset the timer
        if index == self.active_task_index:
            self.active_task_index = -1
        # If we delete a task before the active one, shift the active index down
        elif index < self.active_task_index:
            self.active_task_index -= 1
            
        del self.tasks_data[index]
        self.rebuild_task_list_ui()
        self.update_timer_display()


    def save_data(self, *args):
        if self.active_task_index != -1 and self.active_task_index < len(self.tasks_data):
             self.tasks_data[self.active_task_index]['remaining'] = self.get_current_timer_remaining()
        self.store.put('app_data', 
                       tasks=self.tasks_data,
                       active_index=self.active_task_index)

    def load_data(self, *args):
        if self.store.exists('app_data'):
            data = self.store.get('app_data')
            self.tasks_data = data.get('tasks', [])
            self.active_task_index = data.get('active_index', -1)
            for task in self.tasks_data:
                if 'remaining' not in task:
                    task['remaining'] = task['duration']
            self.update_timer_display()
            self.rebuild_task_list_ui()
    
    def start_timer(self, *args):
        if self.timer_event or self.get_current_timer_remaining() <= 0:
            return
        self.timer_event = Clock.schedule_interval(self.update_timer, 1)

    def pause_timer(self, *args):
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None

    def reset_timer(self, *args):
        self.pause_timer()
        if self.active_task_index != -1:
            active_task = self.tasks_data[self.active_task_index]
            active_task['remaining'] = active_task['duration']
            self.update_timer_display()
    
    def get_current_timer_remaining(self):
        if self.active_task_index == -1 or self.active_task_index >= len(self.tasks_data):
            return 0
        return self.tasks_data[self.active_task_index]['remaining']
    
    def get_current_task_duration(self):
        if self.active_task_index == -1 or self.active_task_index >= len(self.tasks_data):
            return 0
        return self.tasks_data[self.active_task_index]['duration']

    def update_timer(self, dt):
        if self.active_task_index != -1:
            if self.tasks_data[self.active_task_index]['remaining'] > 0:
                self.tasks_data[self.active_task_index]['remaining'] -= 1
                self.update_timer_display()
            else:
                self.pause_timer()
                self.show_alert()

    def show_alert(self):
        # if self.alert_sound:
        #     self.alert_sound.play()
        popup_content = BoxLayout(orientation='vertical', padding=10)
        popup_content.add_widget(Label(text="Time's Up!", font_size='30sp'))
        close_button = Button(text='Dismiss', size_hint_y=None, height='50dp')
        popup_content.add_widget(close_button)
        popup = Popup(title='Alert', content=popup_content, size_hint=(0.7, 0.4), auto_dismiss=False)
        close_button.bind(on_press=popup.dismiss)
        popup.open()

    def update_timer_display(self):
        remaining = self.get_current_timer_remaining()
        duration = self.get_current_task_duration()
        if duration > 0:
            self.progress_fraction = remaining / duration
        else:
            self.progress_fraction = 0
        m, s = divmod(remaining, 60)
        h, m = divmod(m, 60)
        self.timer_text = f'{int(h):02d}:{int(m):02d}:{int(s):02d}'

class MomentumApp(App):
    def on_start(self):
        self.root.load_data()
    def on_stop(self):
        self.root.save_data()
    def build(self):
        return MomentumLayout()

if __name__ == '__main__':
    MomentumApp().run()