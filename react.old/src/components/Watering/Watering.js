import watering_icon from "../../img/watering.png";

const Watering = ({ isReady, stat }) => {
    const amount = (watering) => {
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
                                    <span className="text-start display-1 ms-4" data-testid="watering-amount-info">
                                        <span className="fw-bold digit">{watering.amount.toFixed(1)}</span>
                                        <span className="display-5 ms-2">L</span>
                                    </span>
                                </div>
                                <div className="col-12 mt-3">
                                    <span className="text-start ms-4 text-muted" data-testid="watering-price-info">
                                        <span className="fw-bold display-6 digit">{watering.price.toFixed(1)}</span>
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
    const loading = () => {
        return (
            <div className="card-body outdoor_unit">
                <span className="display-1 align-middle ms-4">
                    <span className="display-5">Loading...</span>
                </span>
            </div>
        );
    };

    return (
        <div class="col">
            <div className="card-deck mb-3 text-center">
                <div className="card mb-4 shadow-sm">
                    <div className="card-header">
                        <h4 className="my-0 font-weight-normal">本日の散水量</h4>
                    </div>
                    {isReady ? amount(stat.watering) : loading()}
                </div>
            </div>
        </div>
    );
};

export default Watering;
