# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'main.ui'
#
# Created by: PyQt5 UI code generator 5.15.6
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(944, 719)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.gridLayout = QtWidgets.QGridLayout(self.centralwidget)
        self.gridLayout.setObjectName("gridLayout")
        self.groupBox_2 = QtWidgets.QGroupBox(self.centralwidget)
        self.groupBox_2.setObjectName("groupBox_2")
        self.gridLayout_4 = QtWidgets.QGridLayout(self.groupBox_2)
        self.gridLayout_4.setObjectName("gridLayout_4")
        self.gridLayout_3 = QtWidgets.QGridLayout()
        self.gridLayout_3.setObjectName("gridLayout_3")
        spacerItem = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.gridLayout_3.addItem(spacerItem, 9, 0, 1, 1)
        self.delete2 = QtWidgets.QPushButton(self.groupBox_2)
        self.delete2.setObjectName("delete2")
        self.gridLayout_3.addWidget(self.delete2, 7, 1, 1, 1)
        self.write1 = QtWidgets.QPushButton(self.groupBox_2)
        self.write1.setObjectName("write1")
        self.gridLayout_3.addWidget(self.write1, 4, 0, 1, 1)
        self.groupBox1 = QtWidgets.QGroupBox(self.groupBox_2)
        self.groupBox1.setObjectName("groupBox1")
        self.gridLayout_5 = QtWidgets.QGridLayout(self.groupBox1)
        self.gridLayout_5.setObjectName("gridLayout_5")
        self.comboBoxPrefix1 = QtWidgets.QComboBox(self.groupBox1)
        self.comboBoxPrefix1.setObjectName("comboBoxPrefix1")
        self.gridLayout_5.addWidget(self.comboBoxPrefix1, 0, 0, 1, 1)
        self.comboBoxSuffix1 = QtWidgets.QComboBox(self.groupBox1)
        self.comboBoxSuffix1.setObjectName("comboBoxSuffix1")
        self.gridLayout_5.addWidget(self.comboBoxSuffix1, 0, 1, 1, 1)
        self.lineEditIRI1 = QtWidgets.QLineEdit(self.groupBox1)
        self.lineEditIRI1.setMinimumSize(QtCore.QSize(100, 0))
        self.lineEditIRI1.setObjectName("lineEditIRI1")
        self.gridLayout_5.addWidget(self.lineEditIRI1, 1, 0, 1, 2)
        self.gridLayout_3.addWidget(self.groupBox1, 3, 0, 1, 2)
        self.write2 = QtWidgets.QPushButton(self.groupBox_2)
        self.write2.setObjectName("write2")
        self.gridLayout_3.addWidget(self.write2, 7, 0, 1, 1)
        self.delete1 = QtWidgets.QPushButton(self.groupBox_2)
        self.delete1.setObjectName("delete1")
        self.gridLayout_3.addWidget(self.delete1, 4, 1, 1, 1)
        self.groupBox2 = QtWidgets.QGroupBox(self.groupBox_2)
        self.groupBox2.setObjectName("groupBox2")
        self.gridLayout_6 = QtWidgets.QGridLayout(self.groupBox2)
        self.gridLayout_6.setObjectName("gridLayout_6")
        self.comboBoxPrefix2 = QtWidgets.QComboBox(self.groupBox2)
        self.comboBoxPrefix2.setObjectName("comboBoxPrefix2")
        self.gridLayout_6.addWidget(self.comboBoxPrefix2, 0, 0, 1, 1)
        self.comboBoxSuffix2 = QtWidgets.QComboBox(self.groupBox2)
        self.comboBoxSuffix2.setObjectName("comboBoxSuffix2")
        self.gridLayout_6.addWidget(self.comboBoxSuffix2, 0, 1, 1, 1)
        self.lineEditIRI2 = QtWidgets.QLineEdit(self.groupBox2)
        self.lineEditIRI2.setObjectName("lineEditIRI2")
        self.gridLayout_6.addWidget(self.lineEditIRI2, 1, 0, 1, 2)
        self.gridLayout_3.addWidget(self.groupBox2, 6, 0, 1, 2)
        spacerItem1 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.gridLayout_3.addItem(spacerItem1, 8, 0, 1, 1)
        spacerItem2 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.gridLayout_3.addItem(spacerItem2, 8, 1, 1, 1)
        self.gridLayout_4.addLayout(self.gridLayout_3, 0, 3, 1, 1)
        self.gridLayout.addWidget(self.groupBox_2, 0, 1, 1, 1)
        self.groupBox = QtWidgets.QGroupBox(self.centralwidget)
        self.groupBox.setObjectName("groupBox")
        self.gridLayout_2 = QtWidgets.QGridLayout(self.groupBox)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.h5TreeWidget = QtWidgets.QTreeWidget(self.groupBox)
        self.h5TreeWidget.setMinimumSize(QtCore.QSize(100, 200))
        self.h5TreeWidget.setObjectName("h5TreeWidget")
        self.h5TreeWidget.headerItem().setText(0, "1")
        self.gridLayout_2.addWidget(self.h5TreeWidget, 0, 0, 1, 1)
        self.gridLayout.addWidget(self.groupBox, 0, 0, 1, 1)
        self.groupBox_3 = QtWidgets.QGroupBox(self.centralwidget)
        self.groupBox_3.setMinimumSize(QtCore.QSize(0, 100))
        self.groupBox_3.setMaximumSize(QtCore.QSize(16777215, 200))
        self.groupBox_3.setObjectName("groupBox_3")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.groupBox_3)
        self.verticalLayout.setObjectName("verticalLayout")
        self.messageTextEdit = QtWidgets.QPlainTextEdit(self.groupBox_3)
        self.messageTextEdit.setEnabled(False)
        self.messageTextEdit.setObjectName("messageTextEdit")
        self.verticalLayout.addWidget(self.messageTextEdit)
        self.gridLayout.addWidget(self.groupBox_3, 1, 0, 1, 2)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 944, 26))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
        self.groupBox_2.setTitle(_translate("MainWindow", "Metadata"))
        self.delete2.setText(_translate("MainWindow", "Delete"))
        self.write1.setText(_translate("MainWindow", "Write"))
        self.groupBox1.setTitle(_translate("MainWindow", "predicate"))
        self.write2.setText(_translate("MainWindow", "Write"))
        self.delete1.setText(_translate("MainWindow", "Delete"))
        self.groupBox2.setTitle(_translate("MainWindow", "object"))
        self.groupBox.setTitle(_translate("MainWindow", "HDF5 file content"))
        self.groupBox_3.setTitle(_translate("MainWindow", "Messages"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())