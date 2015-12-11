"""
    gui/filter
    ~~~~~~~~~~~~~~~~~~~~

    Graphical user interface for picasso.filter

    :author: Joerg Schnitzbauer, 2015
"""


import sys
import traceback
from PyQt4 import QtCore, QtGui
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg, NavigationToolbar2QT
import matplotlib.pyplot as plt
from matplotlib.widgets import SpanSelector, RectangleSelector
from matplotlib.colors import LogNorm
import numpy as np
import os.path
from picasso import io, postprocess


plt.style.use('ggplot')


class TableModel(QtCore.QAbstractTableModel):

    def __init__(self, locs, parent=None):
        super().__init__(parent)
        self.locs = locs

    def columnCount(self, parent):
        try:
            return len(self.locs[0])
        except IndexError:
            return 0

    def rowCount(self, parent):
        return self.locs.shape[0]

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole:
            data = self.locs[index.row()][index.column()]
            return str(data)
        return None

    def headerData(self, section, orientation, role):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self.locs.dtype.names[section]
            elif orientation == QtCore.Qt.Vertical:
                return section
        return None


class TableView(QtGui.QTableView):

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        path = urls[0].toLocalFile()
        extension = os.path.splitext(path)[1].lower()
        if extension == '.hdf5':
            self.window.open(path)


class PlotWindow(QtGui.QWidget):

    def __init__(self, main_window, locs):
        super().__init__()
        self.main_window = main_window
        self.locs = locs
        self.figure = plt.Figure()
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.plot()
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)
        vbox.addWidget(self.canvas)
        vbox.addWidget((NavigationToolbar2QT(self.canvas, self)))
        self.setWindowTitle('Picasso: Filter')

    def update_locs(self, locs):
        self.locs = locs
        self.plot()
        self.update()


class HistWindow(PlotWindow):

    def __init__(self, main_window, locs, field):
        self.field = field
        super().__init__(main_window, locs)

    def plot(self):
        # Prepare the data
        data = self.locs[self.field]
        data = data[np.isfinite(data)]
        bins = postprocess.calculate_optimal_bins(data, 1000)
        # Prepare the figure
        self.figure.clear()
        self.figure.suptitle(self.field)
        axes = self.figure.add_subplot(111)
        axes.hist(data, bins, rwidth=1, linewidth=0)
        data_range = data.ptp()
        axes.set_xlim([bins[0] - 0.05*data_range, data.max() + 0.05*data_range])
        SpanSelector(axes, self.on_span_select, 'horizontal', useblit=True, rectprops=dict(facecolor='green', alpha=0.2))
        self.canvas.draw()

    def on_span_select(self, xmin, xmax):
        self.locs = self.locs[np.isfinite(self.locs[self.field])]
        self.locs = self.locs[(self.locs[self.field] > xmin) & (self.locs[self.field] < xmax)]
        self.main_window.update_locs(self.locs)
        self.main_window.log_filter(self.field, xmin.item(), xmax.item())
        self.plot()

    def closeEvent(self, event):
        self.main_window.hist_windows[self.field] = None
        event.accept()


class Hist2DWindow(PlotWindow):

    def __init__(self, main_window, locs, field_x, field_y):
        self.field_x = field_x
        self.field_y = field_y
        super().__init__(main_window, locs)

    def plot(self):
        # Prepare the data
        x = self.locs[self.field_x]
        y = self.locs[self.field_y]
        valid = (np.isfinite(x) & np.isfinite(y))
        x = x[valid]
        y = y[valid]
        # Prepare the figure
        self.figure.clear()
        axes = self.figure.add_subplot(111)
        # Start hist2 version
        bins_x = postprocess.calculate_optimal_bins(x, 1000)
        bins_y = postprocess.calculate_optimal_bins(y, 1000)
        counts, x_edges, y_edges, image = axes.hist2d(x, y, bins=[bins_x, bins_y], norm=LogNorm())
        x_range = x.ptp()
        axes.set_xlim([bins_x[0] - 0.05*x_range, x.max() + 0.05*x_range])
        y_range = y.ptp()
        axes.set_ylim([bins_y[0] - 0.05*y_range, y.max() + 0.05*y_range])
        self.figure.colorbar(image, ax=axes)
        axes.grid(False)
        axes.get_xaxis().set_label_text(self.field_x)
        axes.get_yaxis().set_label_text(self.field_y)
        self.selector = RectangleSelector(axes, self.on_rect_select, useblit=True, rectprops=dict(facecolor='green',
                                                                                                  alpha=0.2,
                                                                                                  fill=True))
        self.canvas.draw()

    def on_rect_select(self, press_event, release_event):
        x1, y1 = press_event.xdata, press_event.ydata
        x2, y2 = release_event.xdata, release_event.ydata
        xmin = min(x1, x2)
        xmax = max(x1, x2)
        ymin = min(y1, y2)
        ymax = max(y1, y2)
        self.locs = self.locs[np.isfinite(self.locs[self.field_x])]
        self.locs = self.locs[np.isfinite(self.locs[self.field_y])]
        self.locs = self.locs[(self.locs[self.field_x] > xmin) & (self.locs[self.field_x] < xmax)]
        self.locs = self.locs[(self.locs[self.field_y] > ymin) & (self.locs[self.field_y] < ymax)]
        self.main_window.update_locs(self.locs)
        self.main_window.log_filter(self.field_x, xmin, xmax)
        self.main_window.log_filter(self.field_y, ymin, ymax)
        self.plot()

    def closeEvent(self, event):
        self.main_window.hist2d_windows[self.field_x][self.field_y] = None
        event.accept()


class Window(QtGui.QMainWindow):

    def __init__(self):
        super().__init__()
        # Init GUI
        self.setWindowTitle('Picasso: Filter')
        self.resize(1100, 750)
        this_directory = os.path.dirname(os.path.realpath(__file__))
        icon_path = os.path.join(this_directory, 'filter.ico')
        icon = QtGui.QIcon(icon_path)
        self.setWindowIcon(icon)
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu('File')
        open_action = file_menu.addAction('Open')
        open_action.setShortcut(QtGui.QKeySequence.Open)
        open_action.triggered.connect(self.open_file_dialog)
        file_menu.addAction(open_action)
        save_action = file_menu.addAction('Save')
        save_action.setShortcut(QtGui.QKeySequence.Save)
        save_action.triggered.connect(self.save_file_dialog)
        file_menu.addAction(save_action)
        plot_menu = menu_bar.addMenu('Plot')
        histogram_action = plot_menu.addAction('Histogram')
        histogram_action.setShortcut('Ctrl+H')
        histogram_action.triggered.connect(self.plot_histogram)
        scatter_action = plot_menu.addAction('2D Histogram')
        scatter_action.setShortcut('Ctrl+D')
        scatter_action.triggered.connect(self.plot_hist2d)
        self.table_view = TableView(self, self)
        self.table_view.setAcceptDrops(True)
        self.setCentralWidget(self.table_view)
        self.hist_windows = {}
        self.hist2d_windows = {}
        self.filter_log = {}
        self.locs = None

    def open_file_dialog(self):
        path = QtGui.QFileDialog.getOpenFileName(self, 'Open localizations', filter='*.hdf5')
        if path:
            self.open(path)

    def open(self, path):
        locs, self.info = io.load_locs(path)
        if self.locs is not None:
            for field in self.locs.dtype.names:
                if self.hist_windows[field]:
                    self.hist_windows[field].close()
                for field_y in self.locs.dtype.names:
                    if self.hist2d_windows[field][field_y]:
                        self.hist_windows[field][field_y].close()
        self.locs_path = path
        self.update_locs(locs)
        for field in self.locs.dtype.names:
            self.hist_windows[field] = None
            self.hist2d_windows[field] = {}
            for field_y in self.locs.dtype.names:
                self.hist2d_windows[field][field_y] = None
            self.filter_log[field] = None

    def plot_histogram(self):
        selection_model = self.table_view.selectionModel()
        indices = selection_model.selectedColumns()
        if len(indices) > 0:
            for index in indices:
                index = index.column()
                field = self.locs.dtype.names[index]
                if not self.hist_windows[field]:
                    self.hist_windows[field] = HistWindow(self, self.locs, field)
                self.hist_windows[field].show()

    def plot_hist2d(self):
        selection_model = self.table_view.selectionModel()
        indices = selection_model.selectedColumns()
        if len(indices) == 2:
            indices = [index.column() for index in indices]
            field_x, field_y = [self.locs.dtype.names[index] for index in indices]
            if not self.hist2d_windows[field_x][field_y]:
                self.hist2d_windows[field_x][field_y] = Hist2DWindow(self, self.locs, field_x, field_y)
            self.hist2d_windows[field_x][field_y].show()

    def update_locs(self, locs):
        self.locs = locs
        table_model = TableModel(self.locs, self)
        self.table_view.setModel(table_model)
        for field, hist_window in self.hist_windows.items():
            if hist_window:
                hist_window.update_locs(locs)
        for field_x, hist2d_windows in self.hist2d_windows.items():
            for field_y, hist2d_window in hist2d_windows.items():
                if hist2d_window:
                    hist2d_window.update_locs(locs)

    def log_filter(self, field, xmin, xmax):
        if self.filter_log[field]:
            self.filter_log[field][0] = max(xmin, self.filter_log[field][0])
            self.filter_log[field][1] = min(xmax, self.filter_log[field][1])
        else:
            self.filter_log[field] = [xmin, xmax]

    def save_file_dialog(self):
        base, ext = os.path.splitext(self.locs_path)
        out_path = base + '_filter.hdf5'
        path = QtGui.QFileDialog.getSaveFileName(self, 'Save localizations', out_path, filter='*.hdf5')
        if path:
            filter_info = self.filter_log.copy()
            filter_info.update({'Generated by': 'Picasso Filter'})
            info = self.info + [filter_info]
            io.save_locs(path, self.locs, info)

    def closeEvent(self, event):
        QtGui.qApp.closeAllWindows()


if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = Window()
    window.show()

    def excepthook(type, value, tback):
        message = ''.join(traceback.format_exception(type, value, tback))
        errorbox = QtGui.QMessageBox.critical(window, 'An error occured', message)
        errorbox.exec_()
        sys.__excepthook__(type, value, tback)
    sys.excepthook = excepthook

    sys.exit(app.exec_())