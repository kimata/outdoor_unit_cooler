import React from "react";
import watering_icon from "../assets/watering.png";

import { ApiResponse } from "../lib/ApiResponse";
import { Loading } from "./common/Loading";
import { AnimatedNumber } from "./common/AnimatedNumber";
import { StatComponentProps } from "../types/common";

const Watering = React.memo(({ isReady, stat }: StatComponentProps) => {
    const amount = (watering: ApiResponse.Watering) => {
        return (
            <div className="card-body outdoor_unit">
                <div className="container">
                    <div className="row">
                        <div className="col-1">
                            <img src={watering_icon} alt="🚰" width="120px" />
                        </div>
                        <div className="col-11">
                            <div className="row">
                                <div className="col-12">
                                    <span
                                        className="text-start display-1 ms-4"
                                        data-testid="watering-amount-info"
                                    >
                                        <AnimatedNumber
                                            value={watering.amount}
                                            decimals={1}
                                            className="fw-bold digit"
                                        />
                                        <span className="display-5 ms-2">L</span>
                                    </span>
                                </div>
                                <div className="col-12 mt-3">
                                    <span
                                        className="text-start ms-4 text-muted"
                                        data-testid="watering-price-info"
                                    >
                                        <AnimatedNumber
                                            value={watering.price}
                                            decimals={1}
                                            className="fw-bold display-6 digit"
                                        />
                                        <span className="ms-2">円</span>
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        );
    };

    return (
        <div className="col">
            <div className="card-deck mb-3 text-center">
                <div className="card mb-4 shadow-sm">
                    <div className="card-header">
                        <h4 className="my-0 font-weight-normal">本日の散水量</h4>
                    </div>
                    {isReady || stat.watering.length > 0 ? amount(stat.watering[0]) : (
                        <div className="card-body outdoor_unit">
                            <Loading size="large" />
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
});

Watering.displayName = 'Watering';

export { Watering };
