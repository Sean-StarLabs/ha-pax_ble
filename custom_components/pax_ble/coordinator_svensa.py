import datetime as dt
import logging

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .devices.svensa import Svensa

from .coordinator import PaxCoordinator

_LOGGER = logging.getLogger(__name__)

class SvensaCoordinator(PaxCoordinator):
    def __init__(self, hass, device, model, mac, pin, scan_interval, scan_interval_fast):
        """Initialize coordinator parent"""
        super().__init__(hass, device, model, mac, pin, scan_interval, scan_interval_fast)

        # Initialize correct fan
        _LOGGER.debug("Initializing Svansa!")
        self._fan = Svensa(hass, mac, pin)

    async def write_data(self, key) -> bool:
        _LOGGER.debug("Write_Data: %s", key)
        try:
            # Make sure we are connected
            if not await self._fan.connect():
                raise Exception("Not connected!")
        except Exception as e:
            _LOGGER.warning("Error when writing data: %s", str(e))
            return False

        # Authorize
        await self._fan.authorize()

        try:
            # Write data
            match key:
                case "automatic_cycles":
                    await self._fan.setAutomaticCycles(
                        int(self._state["automatic_cycles"])
                    )
                case "boostmode":
                    # Use default values if not set up
                    if int(self._state["boostmodesecwrite"]) == 0:
                        self._state["boostmodespeedwrite"] = 2400
                        self._state["boostmodesecwrite"] = 600
                    await self._fan.setBoostMode(
                        int(self._state["boostmode"]),
                        int(self._state["boostmodespeedwrite"]),
                        int(self._state["boostmodesecwrite"]),
                    )
                case "fanspeed_humidity" | "sensitivity_humidity":
                    await self._fan.setHumidity(
                        int(self._state["sensitivity_humidity"]) != 0,
                        int(self._state["sensitivity_humidity"]),
                        int(self._state["fanspeed_humidity"]),
                    )
                case "fanspeed_light" | "lightsensorsettings_runningtime" | "lightsensorsettings_delayedstart":
                    await self._fan.setTimeFunctions(
                        int(self._state["lightsensorsettings_delayedstart"]),
                        int(self._state["lightsensorsettings_runningtime"]),
                        int(self._state["lightsensorsettings_runningtime"]),
                        int(self._state["fanspeed_light"])
                    )
                case "fanspeed_trickle":
                    await self._fan.setConstantOperation(
                        int(self._state["fanspeed_trickle"]) != 0,
                        int(self._state["fanspeed_trickle"])
                    )            
                case "sensitivity_light":
                    # Should we do anything here?
                    pass
                case "trickledays_weekdays" | "trickledays_weekends":
                    await self._fan.setTrickleDays(
                        int(self._state["trickledays_weekdays"]),
                        int(self._state["trickledays_weekends"]),
                    )
                case "silenthours_on" | "silenthours_starttime" | "silenthours_endtime":
                    await self._fan.setSilentHours(
                        bool(int(self._state["silenthours_on"])),
                        self._state["silenthours_starttime"],
                        self._state["silenthours_endtime"],
                    )

                case _:
                    return False
                
        except Exception as e:
            _LOGGER.debug("Not able to write command: %s", str(e))
            return False

        self.setFastPollMode()
        return True

    async def read_configdata(self, disconnect=False) -> bool:
        _LOGGER.debug("Reading config data")
        try:
            # Make sure we are connected
            if not await self._fan.connect():
                raise Exception("Not connected!")
        except Exception as e:
            _LOGGER.warning("Error when fetching config data: %s", str(e))
            return False

        FanMode = await self._fan.getMode()  # Configuration

        SilentHours = await self._fan.getSilentHours()  # Configuration
        TrickleDays = await self._fan.getTrickleDays()  # Configuration
        AutomaticCycles = await self._fan.getAutomaticCycles()  # Configuration

        if FanMode is None:
            _LOGGER.debug("Could not read config")
            return False
        else:
            self._state["mode"] = FanMode

            self._state["silenthours_on"] = SilentHours.On
            self._state["silenthours_starttime"] = dt.time(SilentHours.StartingHour, SilentHours.StartingMinute)
            self._state["silenthours_endtime"] = dt.time(SilentHours.EndingHour, SilentHours.EndingMinute)

            self._state["trickledays_weekdays"] = TrickleDays.Weekdays
            self._state["trickledays_weekends"] = TrickleDays.Weekends

            self._state["automatic_cycles"] = AutomaticCycles
            
        # Device specific configs
        Humidity =  await self._fan.getHumidity()  # Configuration
        self._state["fanspeed_humidity"] = Humidity.Speed
        self._state["sensitivity_humidity"] = Humidity.Level

        TimeFunctions = await self._fan.getTimeFunctions()  # Configuration
        self._state["fanspeed_light"] = TimeFunctions.Speed
        self._state["lightsensorsettings_delayedstart"] = TimeFunctions.PresenceTime
        self._state["lightsensorsettings_runningtime"] = TimeFunctions.TimeActive

        ConstantOperation = await self._fan.getConstantOperation()  # Configuration
        self._state["fanspeed_trickle"] = ConstantOperation.Speed

        if disconnect:
            await self._fan.disconnect()
        return True
