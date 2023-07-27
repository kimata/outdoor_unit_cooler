export namespace ApiResponse {
    export interface LogEntry {
        id: number;
        date: string;
        message: string;
    }
    export interface Log {
        data: LogEntry[];
        last_time: number;
    }

    export interface CoolerStatus {
        message: string;
        status: number;
    }
    export interface Mode {
        duty: {
            enable: boolean;
            off_sec: number;
            on_sec: number;
        };
        mode_index: number;
        state: number;
    }
    export interface OutdoorStatus {
        message: string;
        status: number;
    }
    export interface SensorData {
        name: string;
        time: string;
        value: number;
    }
    export interface Watering {
        amount: number;
        price: number;
    }

    export interface Stat {
        cooler_status: CoolerStatus;
        outdoor_status: OutdoorStatus;
        mode: Mode;
        sensor: {
            temp: SensorData[];
            humi: SensorData[];
            lux: SensorData[];
            solar_rad: SensorData[];
            power: SensorData[];
        };
        watering: Watering;
    }
}
