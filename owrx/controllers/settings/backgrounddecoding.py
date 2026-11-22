from owrx.controllers.settings import SettingsFormController
from owrx.form.section import Section
from owrx.form.input import CheckboxInput, ServicesCheckboxInput, NumberInput
from owrx.form.input.validator import RangeValidator
from owrx.breadcrumb import Breadcrumb, BreadcrumbItem
from owrx.controllers.settings import SettingsBreadcrumb


class BackgroundDecodingController(SettingsFormController):
    def getTitle(self):
        return "Background decoding"

    def get_breadcrumb(self) -> Breadcrumb:
        return SettingsBreadcrumb().append(BreadcrumbItem("Background decoding", "settings/backgrounddecoding"))

    def getSections(self):
        return [
            Section(
                "Background decoding",
                CheckboxInput(
                    "services_enabled",
                    "Enable background decoding services",
                ),
                ServicesCheckboxInput("services_decoders", "Enabled services"),
            ),
            Section(
                "Signal activity alerts",
                NumberInput(
                    "signal_alert_squelch",
                    "Alert squelch level",
                    validator=RangeValidator(5, 70),
                    infotext="Signal-to-noise ratio (SNR) that triggers an alert",
                    append="dB",
                ),
                NumberInput(
                    "signal_alert_hang_time",
                    "Alert squelch hang time",
                    validator=RangeValidator(0, 5000),
                    infotext="Time the clip keeps recording after the signal disappears",
                    append="ms",
                ),
                NumberInput(
                    "signal_alert_min_duration",
                    "Minimum activity duration",
                    validator=RangeValidator(0, 60000),
                    infotext="Ignore blips shorter than this before sending an alert",
                    append="ms",
                ),
                NumberInput(
                    "signal_alert_cooldown",
                    "Alert cooldown",
                    validator=RangeValidator(0, 3600),
                    infotext="Minimum time between two alerts",
                    append="s",
                ),
                CheckboxInput(
                    "signal_alert_bookmarks",
                    "Monitor scannable bookmarks",
                    infotext="Also raise signal alerts for scannable bookmarks within the SDR bandwidth "
                    + "(requires the signal_alert service to be enabled above)",
                ),
                NumberInput(
                    "signal_alert_bookmarks_max",
                    "Maximum monitored bookmarks",
                    validator=RangeValidator(1, 256),
                    infotext="Per SDR profile; bookmarks nearest to the center frequency are preferred",
                ),
            ),
        ]
