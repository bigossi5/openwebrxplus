from owrx.source.connector import ConnectorSource, ConnectorDeviceDescription
from owrx.command import Flag, Option, Argument
from owrx.form.input import Input
from owrx.form.input.device import RemoteInput, DirectSamplingInput, BiasTeeInput
from owrx.form.input.validator import Range
from typing import List


class RtlTcpSource(ConnectorSource):
    def getCommandMapper(self):
        return (
            super()
            .getCommandMapper()
            .setBase("rtl_tcp_connector")
            .setMappings(
                {
                    "bias_tee": Flag("-b"),
                    "direct_sampling": Option("-e"),
                    "remote": Argument(),
                }
            )
        )


class RtlTcpDeviceDescription(ConnectorDeviceDescription):
    def getName(self):
        return "RTL-SDR device (via rtl_tcp)"

    def getInputs(self) -> List[Input]:
        return super().getInputs() + [RemoteInput(), DirectSamplingInput(), BiasTeeInput()]

    def getDeviceMandatoryKeys(self):
        return super().getDeviceMandatoryKeys() + ["remote"]

    def getDeviceOptionalKeys(self):
        return super().getDeviceOptionalKeys() + ["direct_sampling", "bias_tee"]

    def getProfileOptionalKeys(self):
        return super().getProfileOptionalKeys() + ["direct_sampling", "bias_tee"]

    def getSampleRateRanges(self) -> List[Range]:
        return [Range(250000, 3200000)]
